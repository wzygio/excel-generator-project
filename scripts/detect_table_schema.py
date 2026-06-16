"""Detect an Excel table schema and persist it for Agent runtime use."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE / "src"
for path in (WORKSPACE, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from pydantic import BaseModel  # noqa: E402

from yield_report.infrastructure.code_generator import extract_schema  # noqa: E402


class TableSchemaDetectResult(BaseModel):
    success: bool
    source_path: Path
    schema_path: Path
    error: str = ""


def detect_table_schema(
    file_path: Path,
    *,
    output_dir: Path = Path("docs/references/table_schema"),
    extractor: Callable[[Path], str] = extract_schema,
) -> TableSchemaDetectResult:
    source_path = file_path.expanduser()
    if not source_path.is_absolute():
        source_path = WORKSPACE / source_path
    source_path = source_path.resolve()

    output_path = output_dir
    if not output_path.is_absolute():
        output_path = WORKSPACE / output_path
    output_path.mkdir(parents=True, exist_ok=True)
    schema_path = output_path / f"{_safe_stem(source_path.stem)}.md"

    try:
        schema = extractor(source_path)
        schema_path.write_text(schema, encoding="utf-8")
        return TableSchemaDetectResult(
            success=True,
            source_path=source_path,
            schema_path=schema_path,
        )
    except Exception as exc:
        return TableSchemaDetectResult(
            success=False,
            source_path=source_path,
            schema_path=schema_path,
            error=str(exc),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Excel file to inspect.")
    parser.add_argument(
        "--output-dir",
        default="docs/references/table_schema",
        help="Directory for generated schema markdown.",
    )
    args = parser.parse_args()

    result = detect_table_schema(Path(args.file), output_dir=Path(args.output_dir))
    json.dump(result.model_dump(mode="json"), sys.stdout, ensure_ascii=False, default=str)
    if not result.success:
        raise SystemExit(1)


def _safe_stem(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return cleaned or "table_schema"


if __name__ == "__main__":
    main()
