from pathlib import Path
from typing import Any

from pydantic import BaseModel

try:
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
except NameError:
    PROJECT_ROOT = Path.cwd()

# =============================================================================
# 1. 基础配置基类 (复用您的方案一魔法)
# =============================================================================

class BaseConfig(BaseModel):
    """
    基础配置类 (终极兼容版)。
    既支持 Pydantic 的强类型校验，
    又通过魔术方法完美模拟了 Python 字典的行为，以兼容旧代码。
    """
    class Config:
        # 关键设置：允许运行时添加模型中未定义的字段（解决 runtime_settings 报错）
        extra = 'allow'
        # 允许通过字段名或别名填充
        populate_by_name = True

    # --- 1. 字典核心迭代方法 (解决 .keys() 报错) ---
    def keys(self):
        """模拟字典的 .keys()，返回所有字段名"""
        return self.model_dump(by_alias=True).keys()

    def values(self):
        """模拟字典的 .values()，返回所有字段值"""
        # 注意：这里我们返回 getattr 的结果，保持对象引用，而不是 dump 后的纯数据
        return [getattr(self, k) for k in self.keys()]

    def items(self):
        """模拟字典的 .items()，返回 (key, value) 元组"""
        return [(k, getattr(self, k)) for k in self.keys()]

    # --- 2. 安全的 get 方法 ---
    def get(self, key, default=None):
        """
        模拟字典的 .get()。
        增强逻辑：如果属性存在但值为 None，且 default 不为 None，则返回 default。
        """
        value = getattr(self, key, None)
        if value is None and default is not None:
            return default
        return value if value is not None else default

    # --- 3. 基础字典访问 ---
    def __getitem__(self, item):
        val = getattr(self, item, None)
        if val is None and item not in self.keys():
             # 为了兼容旧代码，这里抛出 KeyError 是标准行为
             # 但如果您的代码习惯依赖 None 返回，可以改为 return None
             # 鉴于 extra='allow'，未定义字段应该能通过 setattr 添加进来
             raise KeyError(f"'{item}' not found in configuration")
        return val

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __contains__(self, key):
        return hasattr(self, key) or key in self.keys()

    # --- 4. 解决 config.update({...}) ---
    def update(self, other_dict: dict[str, Any]):
        for k, v in other_dict.items():
            setattr(self, k, v)

    # --- 5. 兜底方案 ---
    def __getattr__(self, item):
        if item.startswith('__'):
            return super().__getattribute__(item)
        return None

# =============================================================================
# 2. 纯底层浏览器配置
# =============================================================================
class BrowserConfig(BaseConfig):
    """纯粹的浏览器运行参数，毫无业务耦合"""
    headless: bool = False
    timeout: int = 60000
    slow_mo: int = 50
    viewport_width: int = 1920
    viewport_height: int = 1080
    # 👇 新增这一行：允许指定真实的本地浏览器内核
    channel: str | None = None

class WebAutomationConfig(BaseConfig):
    """
    Web 自动化基座层总配置。
    只接收浏览器参数和基础下载路径。
    """
    browser: BrowserConfig
    download_dir: str = "downloads"
