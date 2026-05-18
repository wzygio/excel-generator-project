import logging
import re
import shutil
from pathlib import Path

from packages.web_automation.src.config import WebAutomationConfig
from packages.web_automation.src.infrastructure.browser_manager import BrowserManager

logger = logging.getLogger("DownloadService")

class DownloadService:
    def __init__(self, config: WebAutomationConfig):
        self.base_config = config
        self.download_dir = Path(self.base_config.download_dir)
        # 【新增的核心逻辑】：在确保目录存在之前，先彻底清空里面的历史遗留文件
        self._clear_download_dir()

        # 确保目录结构存在
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.browser_manager = BrowserManager(self.base_config.browser)
        self.page = None

    def _clear_download_dir(self):
        """[内部方法] 清空历史下载文件，防止同名冲突或旧数据污染"""
        if self.download_dir.exists():
            logger.info(f"🧹 正在清空历史下载目录: {self.download_dir} ...")
            for item in self.download_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink()  # 删除文件
                    elif item.is_dir():
                        shutil.rmtree(item)  # 删除子文件夹
                except Exception as e:
                    logger.warning(f"⚠️ 无法删除遗留文件 {item} (可能正被其它程序打开): {e}")

    def start_engine(self):
        """启动底层驱动引擎并赋予高级权限"""
        self.page = self.browser_manager.start_browser()
        return self.page

    def perform_download_action(self, action_callable, file_name: str):
        """
        [核心架构升级] 同步且安全的下载动作执行器。
        使用 expect_download() 替代脆弱的后台全局监听。
        它会一直阻塞，直到下载流稳定建立，完美解决 UUID 临时文件和赛跑问题。
        """
        # 1. 安全处理文件名后缀兜底
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", file_name)
        if not safe_name.lower().endswith(('.xlsx', '.xls', '.csv')):
            safe_name += '.xlsx'

        final_path = self.download_dir / safe_name
        logger.info(f"等待文件流生成，目标文件名: {safe_name} ...")

        try:
            # 2. 【核心修复 2】：使用 with 语句块挂起执行，直到触发下载
            with self.page.expect_download(timeout=60000) as download_info: # type:ignore
                action_callable()  # 执行业务层传进来的点击导出动作

            # 3. 拿到确定的下载对象后，再进行保存
            download = download_info.value
            logger.info("⬇️ 拦截到下载流，正在保存至本地...")
            download.save_as(final_path)
            logger.info(f"✅ 文件保存成功: {final_path}")

        except Exception as e:
            logger.error(f"❌ 下载过程发生异常: {e}")
            raise e

    def _handle_shutdown(self):
        if getattr(self.base_config.browser, 'headless', False):
            logger.info("任务结束，正在关闭浏览器...")
            self.browser_manager.stop_browser()
        else:
            logger.info("任务结束。浏览器保持开启 (非Headless模式)。")
