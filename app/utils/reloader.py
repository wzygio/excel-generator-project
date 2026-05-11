"""
reloader.py: [代码热重载] 模块卸载 + 项目指纹

本模块提供以下能力:
1. 强制卸载受控模块: 在开发过程中重新加载修改过的模块，无需重启 Streamlit
2. 项目指纹 (MD5): 通过扫描关键文件计算 MD5 哈希，使 L2 缓存自动失效

设计原理:
    Streamlit 的 @st.cache_data 基于参数哈希缓存。当代码变更时，由于
    函数代码本身的哈希已变，缓存自然失效。但对于跨进程或磁盘缓存 (如 Parquet 快照)，
    我们需要一个 "项目指纹" 来标识当前代码版本，以决定是否需要刷新。

使用方式:
    from app.utils.reloader import unload_module, get_project_fingerprint

    # 热重载指定模块
    unload_module("yield_report.shared_kernel.config")

    # 获取当前项目指纹
    fingerprint = get_project_fingerprint()
"""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# 受管控的模块前缀列表，只有这些模块可以被安全卸载
_CONTROLLED_PREFIXES = (
    "yield_report.",
    "app.",
)


def unload_module(module_name: str) -> bool:
    """
    强制卸载指定模块及其所有子模块。

    安全规则:
        - 只允许卸载以 yield_report. 或 app. 开头的模块
        - sys.modules 中的内置模块和第三方库不会被卸载

    Args:
        module_name: 要卸载的模块名称

    Returns:
        bool: 是否成功卸载
    """
    if not module_name.startswith(_CONTROLLED_PREFIXES):
        logger.warning(
            "不允许卸载模块 '%s': 不在受控前缀列表中 (%s)",
            module_name,
            _CONTROLLED_PREFIXES,
        )
        return False

    # 收集所有需要卸载的子模块
    to_remove = [
        name
        for name in list(sys.modules.keys())
        if name == module_name or name.startswith(f"{module_name}.")
    ]

    if not to_remove:
        logger.warning("模块 '%s' 未在 sys.modules 中找到", module_name)
        return False

    for name in to_remove:
        del sys.modules[name]

    logger.info(
        "模块热卸载完成: %s (含 %d 个子模块)", module_name, len(to_remove)
    )
    return True


def unload_all_controlled_modules() -> int:
    """
    卸载所有受控模块。用于 Streamlit 热重载场景。

    Returns:
        int: 卸载的模块数量
    """
    count = 0
    for name in list(sys.modules.keys()):
        if name.startswith(_CONTROLLED_PREFIXES):
            del sys.modules[name]
            count += 1

    if count > 0:
        logger.info("热重载: 已卸载 %d 个受控模块", count)
    return count


def get_project_fingerprint(
    watch_patterns: Optional[list[str]] = None,
) -> str:
    """
    计算项目指纹 (MD5 哈希)。

    通过对关键源码文件的内容计算 MD5，生成一个代表当前代码版本的指纹。
    用于 Parquet 快照等 L1 缓存的自动失效判断。

    Args:
        watch_patterns: 要监控的文件 glob 模式列表

    Returns:
        str: 32 位 MD5 十六进制字符串

    示例:
        fingerprint = get_project_fingerprint()
        # 结果示例: "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    """
    if watch_patterns is None:
        watch_patterns = [
            "src/yield_report/**/*.py",
            "app/**/*.py",
            "config/*.yaml",
        ]

    hash_md5 = hashlib.md5(usedforsecurity=False)
    files_to_hash: list[Path] = []

    for pattern in watch_patterns:
        for file_path in Path().glob(pattern):
            if file_path.is_file():
                files_to_hash.append(file_path)

    # 按路径排序以保证结果一致性
    files_to_hash.sort(key=lambda p: str(p))

    for file_path in files_to_hash:
        try:
            content = file_path.read_bytes()
            hash_md5.update(content)
        except (OSError, PermissionError) as e:
            logger.warning("无法读取文件 %s: %s", file_path, e)
            continue

    fingerprint = hash_md5.hexdigest()
    logger.debug("项目指纹计算完成: %s (扫描 %d 个文件)", fingerprint, len(files_to_hash))
    return fingerprint
