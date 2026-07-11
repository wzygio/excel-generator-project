"""Pydantic-backed LocalFileLoader configuration tests."""

from __future__ import annotations

from pathlib import Path

from shared_kernel.config_model import AppConfig
from yield_report.infrastructure.local_file_loader import LocalFileLoader


def _app_config(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "paths": {
                "base_dir": str(tmp_path),
                "resources_dir": str(tmp_path / "resources"),
            },
            "source_files": {
                "ct_exception": {
                    "description": "Configured CT source",
                    "filename": "configured-ct.xlsx",
                    "default_path": "resources/configured-ct.xlsx",
                    "remote_path": str(tmp_path / "remote" / "configured-ct.xlsx"),
                },
                "target_decomposition": {
                    "description": "Configured target source",
                    "filename": "configured-target.xlsx",
                    "default_path": "resources/configured-target.xlsx",
                    "alternate_paths": ["staged/configured-target.xlsx"],
                },
                "gap_template": {
                    "description": "Configured Gap source",
                    "filename": "configured-gap.xlsx",
                    "default_path": "resources/configured-gap.xlsx",
                },
            },
        }
    )


def test_ct_source_uses_configured_remote_and_default_paths(tmp_path: Path) -> None:
    remote = tmp_path / "remote" / "configured-ct.xlsx"
    remote.parent.mkdir(parents=True)
    remote.write_bytes(b"ct")
    loader = LocalFileLoader(_app_config(tmp_path))

    result = loader.ensure_ct_exception_file()

    assert result == (tmp_path / "resources" / "configured-ct.xlsx").resolve()
    assert result.read_bytes() == b"ct"


def test_local_source_uses_configured_alternate_path(tmp_path: Path) -> None:
    alternate = tmp_path / "staged" / "configured-target.xlsx"
    alternate.parent.mkdir(parents=True)
    alternate.write_bytes(b"target")
    loader = LocalFileLoader(_app_config(tmp_path))

    result = loader.ensure_target_decomposition_file()

    assert result == (tmp_path / "resources" / "configured-target.xlsx").resolve()
    assert result.read_bytes() == b"target"


def test_ready_status_uses_configured_filenames(tmp_path: Path) -> None:
    gap = tmp_path / "resources" / "configured-gap.xlsx"
    gap.parent.mkdir(parents=True)
    gap.write_bytes(b"gap")
    loader = LocalFileLoader(_app_config(tmp_path))

    assert loader.check_all_files_ready() == {
        "configured-ct.xlsx": False,
        "configured-target.xlsx": False,
        "configured-gap.xlsx": True,
    }
