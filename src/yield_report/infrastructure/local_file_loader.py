"""
local_file_loader.py: 本地/网络文件加载器

负责处理不需要通过 FineReport 获取的本地文件和网络共享文件。
具体文件名、默认路径、备用路径和远端路径来自 Pydantic 校验后的源表目录。

核心功能:
- 检查本地文件是否存在
- 从网络共享路径复制文件到本地 resources/ 目录
- 确认文件就绪状态
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Mapping
from pathlib import Path

from shared_kernel.config import ConfigLoader
from shared_kernel.config_model import AppConfig, SourceFileConfig

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

    def __init__(
        self,
        app_config: AppConfig | None = None,
        source_files: Mapping[str, SourceFileConfig] | None = None,
    ) -> None:
        app_config = app_config or ConfigLoader().get()
        base_dir = Path(app_config.paths.base_dir).expanduser()
        self._base_dir = base_dir.resolve()
        resources_dir = Path(app_config.paths.resources_dir).expanduser()
        self._resources_dir = (
            resources_dir.resolve()
            if resources_dir.is_absolute()
            else (self._base_dir / resources_dir).resolve()
        )
        catalog = source_files if source_files is not None else app_config.source_files
        self._source_files = dict(catalog)

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
        source = self._require_source("ct_exception")
        local_path = self._configured_path(source.default_path, alias="ct_exception")

        # 如果文件已存在且不强制复制，直接返回
        if local_path.exists() and not force_copy:
            logger.info("CT异常管理表已就绪 (本地): %s", local_path)
            return local_path

        # 尝试从网络路径复制
        if not source.remote_path.strip():
            raise LocalFileNotFoundError("source_files.ct_exception.remote_path is not configured")
        network_path = Path(source.remote_path).expanduser()
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
        source = self._require_source("target_decomposition")
        local_path = self._configured_path(
            source.default_path,
            alias="target_decomposition",
        )

        if local_path.exists():
            logger.info("良率目标拆解表已就绪: %s", local_path)
            return local_path

        for alt_path in self._alternate_paths(source):
            if alt_path.exists():
                self._copy_file(alt_path, local_path)
                logger.info("良率目标拆解表已从备用路径复制: %s", local_path)
                return local_path

        raise LocalFileNotFoundError(
            f"良率目标拆解表未找到。"
            f"请将 '{source.filename}' 放置于 {local_path.parent} 目录下。"
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
        source = self._require_source("gap_template")
        local_path = self._configured_path(source.default_path, alias="gap_template")

        if local_path.exists():
            logger.info("日良率Gap分析模板已就绪: %s", local_path)
            return local_path

        for alt_path in self._alternate_paths(source):
            if alt_path.exists():
                self._copy_file(alt_path, local_path)
                logger.info("日良率Gap分析模板已从备用路径复制: %s", local_path)
                return local_path

        raise LocalFileNotFoundError(
            f"日良率Gap分析模板未找到。"
            f"请将 '{source.filename}' 放置于 {local_path.parent} 目录下。"
        )

    def check_all_files_ready(self) -> dict[str, bool]:
        """
        检查所有本地源文件的就绪状态。

        Returns:
            dict: {文件名: 是否存在}
        """
        status: dict[str, bool] = {}
        for alias in ("ct_exception", "target_decomposition", "gap_template"):
            source = self._require_source(alias)
            filepath = self._configured_path(source.default_path, alias=alias)
            status[source.filename or filepath.name] = filepath.exists()

        return status

    # ================================================================
    # 辅助方法
    # ================================================================

    def _require_source(self, alias: str) -> SourceFileConfig:
        source = self._source_files.get(alias)
        if source is None:
            raise ValueError(f"source_files.{alias} is not configured")
        if not source.default_path.strip():
            raise ValueError(f"source_files.{alias}.default_path is not configured")
        return source

    def _configured_path(self, raw_path: str, *, alias: str) -> Path:
        if not raw_path.strip():
            raise ValueError(f"source_files.{alias}.default_path is not configured")
        path = Path(raw_path).expanduser()
        return path.resolve() if path.is_absolute() else (self._base_dir / path).resolve()

    def _alternate_paths(self, source: SourceFileConfig) -> list[Path]:
        paths: list[Path] = []
        for raw_path in source.alternate_paths:
            path = Path(raw_path).expanduser()
            paths.append(
                path.resolve() if path.is_absolute() else (self._base_dir / path).resolve()
            )
        return paths

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
