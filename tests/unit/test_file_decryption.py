"""文件解密工具测试。"""

from __future__ import annotations

from pathlib import Path

from yield_report.infrastructure.file_decryption import decrypt_excel_file


def test_decrypt_excel_file_copies_standard_xlsx_to_output_dir(tmp_path: Path) -> None:
    source = tmp_path / "report.xlsx"
    output_dir = tmp_path / "decrypted_files"
    source.write_bytes(b"PK\x03\x04xlsx-content")

    result = decrypt_excel_file(source, output_dir)

    assert result == output_dir / "report.xlsx"
    assert result.read_bytes() == b"PK\x03\x04xlsx-content"
    assert source.exists()
