"""
llm_handler.py: LLMManager 单例

本模块实现了 DeepSeek / Gemini API 调用的统一管理器。
遵循以下设计原则:
1. 单例模式: 通过 __new__ 实现，全局唯一实例
2. 延迟加载: API Key 在首次调用 chat() 时才从 .env 读取，支持热更新
3. 重试机制: 基于 tenacity 实现指数退避重试
4. 多供应商: deepseek (OpenAI SDK) / gemini (google-genai SDK)

使用的 Prompt:
    本模块不包含业务 Prompt。业务 Prompt 由 Core 层的分析模块定义。
    本模块仅负责将输入的 messages 发送到对应的 LLM API 并返回结果。

约束:
    仅允许使用 DeepSeek 或 Gemini API，禁止引入其他第三方模型 API。

使用方式:
    from yield_report.shared_kernel.infrastructure.llm_handler import llm_manager

    # DeepSeek
    response = llm_manager.chat(
        provider="deepseek",
        messages=[{"role": "user", "content": "Hello"}],
    )

    # Gemini
    response = llm_manager.chat(
        provider="gemini",
        messages=[{"role": "user", "content": "Hello"}],
    )
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM 调用基础异常"""


class LLMConfigurationError(LLMError):
    """LLM 配置异常（如 API Key 未设置）"""


class LLMProviderError(LLMError):
    """LLM 供应商返回异常"""


class LLMManager:
    """
    LLM API 调用管理器 (单例)

    支持 DeepSeek (通过 OpenAI SDK) 和 Gemini (通过 google-genai SDK)。
    使用 __new__ 实现单例模式，并内置失败重试机制。

    线程安全说明:
        单例模式下不维护会话状态，每次 chat() 调用独立创建客户端。
        因此天然支持多线程场景，无需额外的锁机制。
    """

    _instance: LLMManager | None = None

    def __new__(cls, *args, **kwargs) -> LLMManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._deepseek_client: Any = None
        self._gemini_client: Any = None

    # -------- 客户端懒加载 --------

    def _get_deepseek_client(self):
        """懒加载 DeepSeek 客户端 (OpenAI SDK 兼容)。"""
        if self._deepseek_client is not None:
            return self._deepseek_client

        load_dotenv()
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

        if not api_key:
            raise LLMConfigurationError(
                "DEEPSEEK_API_KEY 未设置。请在 .env 文件中配置后再试。"
            )

        try:
            from openai import OpenAI

            self._deepseek_client = OpenAI(api_key=api_key, base_url=base_url)
            logger.info("DeepSeek 客户端初始化成功 (base_url=%s)", base_url)
        except ImportError:
            raise LLMConfigurationError(
                "缺少 openai 库。请执行: uv add openai"
            )
        return self._deepseek_client

    def _get_gemini_client(self):
        """懒加载 Gemini 客户端 (google-genai SDK)。"""
        if self._gemini_client is not None:
            return self._gemini_client

        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise LLMConfigurationError(
                "GEMINI_API_KEY 未设置。请在 .env 文件中配置后再试。"
            )

        try:
            from google import genai

            self._gemini_client = genai.Client(api_key=api_key)
            logger.info("Gemini 客户端初始化成功")
        except ImportError:
            raise LLMConfigurationError(
                "缺少 google-genai 库。请执行: uv add google-genai"
            )
        return self._gemini_client

    # -------- 重试装饰器 --------

    def _build_retry_decorator(self):
        """构建统一的指数退避重试装饰器。"""
        return retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type(
                (LLMProviderError, ConnectionError, TimeoutError)
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

    # -------- 核心调用方法 --------

    def chat(
        self,
        provider: str = "deepseek",
        messages: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> str:
        """
        发送聊天请求到指定的 LLM。

        Args:
            provider: "deepseek" 或 "gemini"
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            system_prompt: 系统提示词（仅 DeepSeek 支持）
            temperature: 生成温度 (0.0 ~ 2.0)
            max_tokens: 最大生成 Token 数
            **kwargs: 传递给底层 API 的额外参数

        Returns:
            str: LLM 返回的文本内容

        Raises:
            LLMConfigurationError: API Key 未配置或 SDK 缺失
            LLMProviderError: API 调用失败
        """
        provider = provider.lower().strip()
        if provider not in ("deepseek", "gemini"):
            raise ValueError(f"不支持的 provider: {provider}，仅支持 deepseek / gemini")

        messages = messages or [{"role": "user", "content": "Hello"}]

        retry_decorator = self._build_retry_decorator()

        if provider == "deepseek":
            return self._call_deepseek(
                messages, system_prompt, temperature, max_tokens, retry_decorator, **kwargs
            )
        else:
            return self._call_gemini(
                messages, temperature, max_tokens, retry_decorator, **kwargs
            )

    def _call_deepseek(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        retry_decorator,
        **kwargs,
    ) -> str:
        """调用 DeepSeek API。"""
        client = self._get_deepseek_client()

        # 构建消息列表
        api_messages = list(messages)
        if system_prompt:
            api_messages.insert(
                0, {"role": "system", "content": system_prompt}
            )

        @retry_decorator
        def _do_call():
            try:
                response = client.chat.completions.create(
                    model=kwargs.pop("model", "deepseek-chat"),
                    messages=api_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                raise LLMProviderError(f"DeepSeek API 调用失败: {e}") from e

        return _do_call()

    def _call_gemini(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        retry_decorator,
        **kwargs,
    ) -> str:
        """调用 Gemini API。"""
        client = self._get_gemini_client()
        model_name = kwargs.pop("model", "gemini-2.0-flash")

        # 将 messages 格式转换为 Gemini 格式
        gemini_contents = []
        for msg in messages:
            role = "user" if msg["role"] in ("user", "system") else "model"
            gemini_contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        @retry_decorator
        def _do_call():
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=gemini_contents,
                    config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                        **kwargs,
                    },
                )
                return response.text or ""
            except Exception as e:
                raise LLMProviderError(f"Gemini API 调用失败: {e}") from e

        return _do_call()

    def chat_stream(
        self,
        provider: str = "deepseek",
        messages: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ):
        """
        流式聊天请求（返回生成器）。

        目前仅 DeepSeek (OpenAI SDK) 支持流式。
        Gemini 的流式支持将在后续版本添加。
        """
        provider = provider.lower().strip()
        if provider != "deepseek":
            raise NotImplementedError(
                f"流式模式暂不支持 {provider}，仅 deepseek 支持"
            )

        client = self._get_deepseek_client()
        api_messages = list(messages or [])
        if system_prompt:
            api_messages.insert(0, {"role": "system", "content": system_prompt})

        response = client.chat.completions.create(
            model=kwargs.pop("model", "deepseek-chat"),
            messages=api_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs,
        )

        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    def clear_clients(self):
        """清除客户端缓存（用于热重载或 API Key 更新）。"""
        self._deepseek_client = None
        self._gemini_client = None
        logger.info("LLM 客户端缓存已清除")


# ======== 模块级单例 ========
llm_manager = LLMManager()
"""
全局 LLM 管理器单例。

使用方式:
    from yield_report.shared_kernel.infrastructure.llm_handler import llm_manager
    reply = llm_manager.chat("deepseek", [{"role": "user", "content": "你好"}])
    print(reply)
"""
