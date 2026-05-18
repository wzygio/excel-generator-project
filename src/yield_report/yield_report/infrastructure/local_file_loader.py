"""
local_file_loader.py: 本地/网络文件加载器

负责处理不需要通过 FineReport 爬取的本地文件和网络共享文件:
1. CT良率异常波动管理表 - 网络路径 (\\10.71.4.18\\...)
2. 良率目标拆解表 - resources/ 本地
3. 日良率Gap分析模板 - resources/ 本地

核心功能:
- 检查本地文件是否存在
- 从网络共享路径复制文件到本地 resources/ 目录
- 确认文件就绪状态
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from yield_report.shared_kernel.config import config as config_loader

logger = logging.getLogger(__name__)


class LocalFileNotFoundError(FileNotFoundError):
    """本地文件未找到"""


class NetworkFileCopyError(Exception):
    """网络文件复制失败"""


class LocalFileLoader:
    """
    本地/网络文件加载器

    负责检查、复制、确认各本地源文件的就绪状态。
    所有文件最终指向 resources/ 目录下的预期路径。
    """

    # 文件定义: (预期文件名, 描述)
    CT_EXCEPTION_FILENAME = "CT良率异常波动管理表.xlsx"
    TARGET_DECOMPOSITION_FILENAME = "2026年良率目标拆解-1017版V05 - 无公式版.xlsx"
    GAP_TEMPLATE_FILENAME = "日良率Gap分析模板.xlsx"

    # CT 异常表的网络共享路径
    CT_EXCEPTION_NETWORK_PATH = (
        r"\\10.71.4.18\合肥维信诺公共盘\23专项\大数据专项"
        r"\02 量产良率\02 良率异常闭环管理\CT良率异常波动管理表.xlsx"
    )

    def __init__(self) -> None:
        app_config = config_loader.get()
        self._resources_dir = Path(app_config.paths.resources_dir)

    # ================================================================
    # 公共方法
    # ================================================================

    def ensure_ct_exception_file(self, force_copy: bool = False) -> Path:
        """
        确保 CT 异常管理表就绪。

        如果本地 resources/ 中不存在该文件，则从网络路径复制。
        如果网络路径不可达，则检查是否已有本地副本。

        Args:
            force_copy: 是否强制从网络路径重新复制

        Returns:
            Path: 本地文件路径

        Raises:
            LocalFileNotFoundError: 文件无法获取
            NetworkFileCopyError: 网络复制失败
        """
        local_path = self._resources_dir / self.CT_EXCEPTION_FILENAME

        # 如果文件已存在且不强制复制，直接返回
        if local_path.exists() and not force_copy:
            logger.info("CT异常管理表已就绪 (本地): %s", local_path)
            return local_path

        # 尝试从网络路径复制
        network_path = Path(self.CT_EXCEPTION_NETWORK_PATH)
        if network_path.exists():
            try:
                self._copy_file(network_path, local_path)
                logger.info("CT异常管理表已从网络路径复制: %s", local_path)
                return local_path
            except Exception as e:
                raise NetworkFileCopyError(
                    f"从网络路径复制 CT异常管理表失败: {e}"
                ) from e
        else:
            raise LocalFileNotFoundError(
                f"CT异常管理表既不在本地 ({local_path})，"
                f"也不在网络路径 ({network_path})。"
                f"请手动检查网络连接或将文件复制到 {local_path}"
            )

    def ensure_target_decomposition_file(self) -> Path:
        """
        确保良率目标拆解表就绪。

        该文件位于 resources/ 目录下，预期已存在。
        如果不存在，给出明确的引导提示。

        Returns:
            Path: 本地文件路径

        Raises:
            LocalFileNotFoundError: 文件未找到
        """
        local_path = self._resources_dir / self.TARGET_DECOMPOSITION_FILENAME

        if local_path.exists():
            logger.info("良率目标拆解表已就绪: %s", local_path)
            return local_path

        # 尝试在 resources/project_files/ 下查找
        alt_path = self._resources_dir / "project_files" / self.TARGET_DECOMPOSITION_FILENAME
        if alt_path.exists():
            # 复制到 resources/ 根目录
            shutil.copy2(str(alt_path), str(local_path))
            logger.info("良率目标拆解表已从 project_files/ 复制: %s", local_path)
            return local_path

        raise LocalFileNotFoundError(
            f"良率目标拆解表未找到。"
            f"请将 '{self.TARGET_DECOMPOSITION_FILENAME}' "
            f"放置于 {self._resources_dir} 目录下。"
        )

    def ensure_gap_template_file(self) -> Path:
        """
        确保日良率Gap分析模板就绪。

        该文件位于 resources/ 目录下，预期已存在。
        如果不存在，给出明确的引导提示。

        Returns:
            Path: 本地文件路径

        Raises:
            LocalFileNotFoundError: 文件未找到
        """
        local_path = self._resources_dir / self.GAP_TEMPLATE_FILENAME

        if local_path.exists():
            logger.info("日良率Gap分析模板已就绪: %s", local_path)
            return local_path

        # 尝试在 resources/project_files/ 下查找
        alt_path = self._resources_dir / "project_files" / self.GAP_TEMPLATE_FILENAME
        if alt_path.exists():
            shutil.copy2(str(alt_path), str(local_path))
            logger.info("日良率Gap分析模板已从 project_files/ 复制: %s", local_path)
            return local_path

        raise LocalFileNotFoundError(
            f"日良率Gap分析模板未找到。"
            f"请将 '{self.GAP_TEMPLATE_FILENAME}' "
            f"放置于 {self._resources_dir} 目录下。"
        )

    def check_all_files_ready(self) -> dict[str, bool]:
        """
        检查所有本地源文件的就绪状态。

        Returns:
            dict: {文件名: 是否存在}
        """
        files = [
            self.CT_EXCEPTION_FILENAME,
            self.TARGET_DECOMPOSITION_FILENAME,
            self.GAP_TEMPLATE_FILENAME,
        ]

        status: dict[str, bool] = {}
        for filename in files:
            filepath = self._resources_dir / filename
            status[filename] = filepath.exists()

        return status

    # ================================================================
    # 辅助方法
    # ================================================================

    @staticmethod
    def _copy_file(source: Path, destination: Path) -> None:
        """
        复制文件，自动创建目标目录。

        Args:
            source: 源文件路径
            destination: 目标文件路径
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(destination))
        logger.debug("文件复制完成: %s -> %s", source, destination)
