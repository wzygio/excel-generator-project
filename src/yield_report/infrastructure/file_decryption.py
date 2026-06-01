"""Excel file decryption/normalization utilities.

This module is the project-facing compatibility wrapper. It prefers the reusable
``fr_file_decryption`` package when that package is installed, and falls back to
the local Excel COM implementation otherwise.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

XLSX_MAGIC = b"PK\x03\x04"


class FileDecryptionError(Exception):
    """Raised when an Excel file cannot be decrypted or normalized."""


def decrypt_excel_file(source_path: Path, output_dir: Path) -> Path:
    """Decrypt or normalize an Excel file into ``output_dir`` and return the output path."""
    source_path = Path(source_path)
    output_dir = Path(output_dir)

    if not source_path.exists():
        raise FileDecryptionError(f"Source file does not exist: {source_path}")
    if not source_path.is_file():
        raise FileDecryptionError(f"Source path is not a file: {source_path}")

    package_output = _try_fr_file_decryption(source_path, output_dir)
    if package_output is not None:
        return package_output

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / source_path.name

    if _is_standard_xlsx(source_path):
        _copy_file(source_path, output_path)
        logger.info("Standard xlsx copied to decrypted directory: %s", output_path)
        return output_path

    logger.info("Potential encrypted xlsx detected; using Excel COM: %s", source_path)
    _decrypt_with_excel_com(source_path, output_path)

    if not _is_standard_xlsx(output_path):
        raise FileDecryptionError(f"Decrypted output is not a standard xlsx: {output_path}")

    logger.info("Excel file decrypted: %s", output_path)
    return output_path


def _try_fr_file_decryption(source_path: Path, output_dir: Path) -> Path | None:
    try:
        from fr_file_decryption import decrypt_file  # type: ignore[import-not-found]
    except ImportError:
        return None

    try:
        result = decrypt_file(source_path, output_dir=output_dir)
    except Exception as exc:
        raise FileDecryptionError(f"fr_file_decryption failed: {exc}") from exc

    output_path = Path(result.output_path)
    logger.info("fr_file_decryption output: %s", output_path)
    return output_path


def _is_standard_xlsx(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            return file.read(4) == XLSX_MAGIC
    except OSError:
        return False


def _copy_file(source_path: Path, output_path: Path) -> None:
    if source_path.resolve() == output_path.resolve():
        return
    if output_path.exists():
        output_path.unlink()
    shutil.copy2(source_path, output_path)


def _decrypt_with_excel_com(source_path: Path, output_path: Path) -> None:
    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError as exc:
        raise FileDecryptionError("pywin32 is required for Excel COM decryption") from exc

    excel = None
    workbook = None
    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        workbook = excel.Workbooks.Open(str(source_path.resolve()))
        if output_path.exists():
            output_path.unlink()

        workbook.SaveAs(str(output_path.resolve()), FileFormat=51)
        workbook.Close(SaveChanges=False)
        workbook = None
    except Exception as exc:
        raise FileDecryptionError(f"Excel COM decryption failed: {exc}") from exc
    finally:
        if workbook is not None:
            try:
                workbook.Close(SaveChanges=False)
            except Exception:
                pass
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass
