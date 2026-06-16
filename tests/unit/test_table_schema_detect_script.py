from __future__ import annotations

from pathlib import Path

from scripts.detect_table_schema import detect_table_schema


def test_detect_table_schema_writes_schema_markdown(tmp_path: Path) -> None:
    source = tmp_path / "V3良率及不良率By月周天汇总报表.xlsx"
    source.write_bytes(b"PK\x03\x04")
    output_dir = tmp_path / "docs" / "references" / "table_schema"

    result = detect_table_schema(
        source,
        output_dir=output_dir,
        extractor=lambda path: f"schema for {path.name}",
    )

    assert result.success is True
    assert result.schema_path == output_dir / "V3良率及不良率By月周天汇总报表.md"
    assert result.schema_path.read_text(encoding="utf-8") == "schema for V3良率及不良率By月周天汇总报表.xlsx"
