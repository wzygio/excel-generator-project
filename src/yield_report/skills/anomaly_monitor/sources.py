"""Source resolution and Spotfire-style table construction for anomaly-monitor inputs."""

# pyright: reportAttributeAccessIssue=false, reportOperatorIssue=false, reportArgumentType=false, reportInvalidTypeArguments=false, reportCallIssue=false

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from yield_report.infrastructure.excel_reader import ExcelReadError, ExcelSheetReader
from yield_report.skills.anomaly_monitor.models import AnomalyMonitorRequest

SOURCE_ALIASES = {
    "data_source_dir",
    "spotfire",
    "hl_raw",
    "batch_yield",
    "hl_history",
    "ct_yield",
    "mwdl_raw",
    "defect_group_dict",
    "daily_anomaly_initial",
    "ct_exception",
    "batch_history",
    "ct_concentration",
    "ct_map_ng",
    "ct_map_ratio",
    "owner_mapping",
}
OPTIONAL_SOURCE_ALIASES = {
    "spotfire",
    "hl_history",
    "defect_group_dict",
    "ct_exception",
    "ct_concentration",
    "ct_map_ng",
    "ct_map_ratio",
    "owner_mapping",
}
CSV_ENCODINGS = ("utf-8-sig", "gbk", "gb18030", "utf-16")
PRODUCT_MODEL_PATTERN = re.compile(r"(?<![A-Z0-9])[A-Z]\d{3,4}(?![A-Z0-9])", re.IGNORECASE)
COMBINED_PRODUCT_PATTERN = re.compile(
    r"^[A-Z]\d{3,4}(?:[&+/][A-Z]\d{3,4})+$",
    re.IGNORECASE,
)
DEFAULT_SHARED_DATA_DIR = Path(
    "//10.71.7.15/"
    "\u5927\u6570\u636e\u5171\u4eab/"
    "12.\u826f\u7387\u76d1\u63a7\u65e5\u62a5\u81ea\u52a8\u5316"
)
DEFAULT_SPOTFIRE_PATH = Path(
    "D:/wzy/"
    "\u5de5\u4f5c-\u503c\u73ed\u5de5\u4f5c/"
    "\u76f8\u5173\u6587\u4ef6/resources/spotfire.xlsx"
)
SHARED_SOURCE_FILES = {
    "hl_raw": "hl_data.csv",
    "batch_yield": "batch_yield_data.csv",
    "hl_history": "hl_csv_data.csv",
    "ct_yield": "ct_yield_data.csv",
    "mwdl_raw": "mwdl_data.csv",
    "defect_group_dict": "imp_ct_dft_group.csv",
}


def load_anomaly_sources(
    request: AnomalyMonitorRequest,
    *,
    workspace: Path,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Load inline rows and build anomaly-monitor tables from source CSVs."""
    warnings: list[str] = []
    sources: dict[str, list[dict[str, Any]]] = {
        "daily_anomaly_initial": list(request.initial_rows),
        "ct_exception": list(request.ct_exception_rows),
        "batch_history": list(request.batch_history_rows),
        "ct_concentration": list(request.detail_rows),
    }
    reader = ExcelSheetReader()
    has_inline_sources = any(
        [
            request.initial_rows,
            request.ct_exception_rows,
            request.batch_history_rows,
            request.detail_rows,
        ]
    )
    source_files = _default_source_files(
        request.source_files,
        workspace,
        use_default_shared=not has_inline_sources,
    )
    product_models = _resolve_product_models(request, source_files, workspace, reader, warnings)

    for alias, raw_path in source_files.items():
        if alias not in SOURCE_ALIASES or alias in {"data_source_dir", "spotfire"}:
            continue
        if sources.get(alias):
            continue
        path = _resolve_path(raw_path, workspace)
        if alias in OPTIONAL_SOURCE_ALIASES and not path.exists():
            continue
        try:
            if alias == "ct_yield":
                sources["ct_concentration"] = _load_ct_yield_detail(path)
                continue
            sources[alias] = _load_table(path, reader=reader)
        except (OSError, ValueError, ExcelReadError) as exc:
            warnings.append(f"读取源表失败({alias}): {exc}")
            sources.setdefault(alias, [])

    if sources.get("ct_exception"):
        sources["ct_exception"] = _normalize_ct_exception_rows(sources["ct_exception"])

    if not sources.get("daily_anomaly_initial") and sources.get("hl_raw"):
        sources["daily_anomaly_initial"] = _build_hl_candidates(
            sources.get("hl_raw", []),
            sources.get("batch_yield", []),
            sources.get("hl_history", []),
            product_models=product_models,
        )
    elif product_models:
        sources["daily_anomaly_initial"] = _filter_product_models(
            sources.get("daily_anomaly_initial", []),
            product_models,
        )

    if sources.get("mwdl_raw"):
        sources["daily_anomaly_initial"].extend(
            _build_mwdl_candidates(
                sources.get("mwdl_raw", []),
                sources.get("batch_yield", []),
                existing_rows=sources.get("daily_anomaly_initial", []),
                product_models=product_models,
            )
        )

    if not sources.get("batch_history") and sources.get("mwdl_raw"):
        sources["batch_history"] = _build_mwdl_history(
            sources.get("mwdl_raw", []),
            sources.get("defect_group_dict", []),
            sources.get("batch_yield", []),
        )

    if not sources.get("ct_concentration") and sources.get("ct_yield"):
        sources["ct_concentration"] = _build_ct_yield_detail(sources["ct_yield"])

    return sources, warnings


def _load_table(path: Path, *, reader: ExcelSheetReader) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [dict(item) for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            rows = data.get("rows") or data.get("data") or []
            return [dict(item) for item in rows if isinstance(item, dict)]
        return []
    if suffix == ".csv":
        return _read_csv_rows(path)
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        sheet = reader.read_sheet(path)
        return _rows_to_dicts(sheet.rows)
    return []


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for encoding in CSV_ENCODINGS:
        try:
            frame = pd.read_csv(path, encoding=encoding)
            frame.columns = [str(column).strip() for column in frame.columns]
            return frame.where(pd.notna(frame), None).to_dict("records")
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except Exception as exc:
            last_error = exc
            continue
    raise ValueError(f"无法读取 CSV 文件: {path}; last_error={last_error}")


def _load_ct_yield_detail(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() != ".csv":
        return _build_ct_yield_detail(_load_table(path, reader=ExcelSheetReader()))
    last_error: Exception | None = None
    for encoding in CSV_ENCODINGS:
        try:
            chunks: list[pd.DataFrame] = []
            for chunk in pd.read_csv(path, encoding=encoding, chunksize=100_000):
                chunk.columns = [str(column).strip() for column in chunk.columns]
                if "ng_qty" in chunk.columns:
                    ng_qty = pd.to_numeric(chunk["ng_qty"], errors="coerce").fillna(0)
                    chunk = chunk[ng_qty > 0].copy()
                if not chunk.empty:
                    chunks.append(chunk)
            if not chunks:
                return []
            frame = pd.concat(chunks, ignore_index=True)
            return _build_ct_yield_detail(frame.where(pd.notna(frame), None).to_dict("records"))
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except Exception as exc:
            last_error = exc
            continue
    raise ValueError(f"无法读取 CT 明细 CSV 文件: {path}; last_error={last_error}")


def _rows_to_dicts(rows: list[list[Any]]) -> list[dict[str, Any]]:
    header_index = None
    for index, row in enumerate(rows[:10]):
        values = [str(value).strip() if value is not None else "" for value in row]
        if any(values):
            header_index = index
            break
    if header_index is None:
        return []
    headers = [
        str(value).strip() if value is not None and str(value).strip() else f"col_{idx}"
        for idx, value in enumerate(rows[header_index])
    ]
    records: list[dict[str, Any]] = []
    for row in rows[header_index + 1 :]:
        if not any(value is not None and str(value).strip() for value in row):
            continue
        records.append({headers[index]: value for index, value in enumerate(row[: len(headers)])})
    return records


def _resolve_path(path: Path, workspace: Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else workspace / candidate


def _default_source_files(
    source_files: dict[str, Path],
    workspace: Path,
    *,
    use_default_shared: bool,
) -> dict[str, Path]:
    resolved = dict(source_files)
    raw_data_dir = resolved.get("data_source_dir")
    data_dir = _resolve_path(raw_data_dir, workspace) if raw_data_dir else DEFAULT_SHARED_DATA_DIR
    should_expand_shared = use_default_shared and (not source_files or raw_data_dir is not None)
    if should_expand_shared and data_dir.exists():
        for alias, filename in SHARED_SOURCE_FILES.items():
            resolved.setdefault(alias, data_dir / filename)
    if (
        should_expand_shared
        and raw_data_dir is None
        and "spotfire" not in resolved
        and DEFAULT_SPOTFIRE_PATH.exists()
    ):
        resolved["spotfire"] = DEFAULT_SPOTFIRE_PATH
    return resolved


def _resolve_product_models(
    request: AnomalyMonitorRequest,
    source_files: dict[str, Path],
    workspace: Path,
    reader: ExcelSheetReader,
    warnings: list[str],
) -> list[str]:
    if request.product_models:
        return list(request.product_models)
    raw_path = source_files.get("spotfire")
    if raw_path is None:
        warnings.append("未提供 product_models 且未找到当日过货表，使用全部候选产品。")
        return []
    path = _resolve_path(raw_path, workspace)
    try:
        products = _load_spotfire_products(path, reader=reader)
    except (OSError, ValueError, ExcelReadError) as exc:
        warnings.append(f"读取当日过货表失败(spotfire): {exc}，使用全部候选产品。")
        return []
    return products


def _load_spotfire_products(path: Path, *, reader: ExcelSheetReader) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"spotfire.xlsx 文件未找到: {path}")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        rows = _read_csv_rows(path)
        return _dedupe_products(_first_text(row, "prod_code", "产品型号", "产品") for row in rows)
    sheet = reader.read_sheet(path)
    products: list[str] = []
    for row in sheet.rows[1:]:
        if not row:
            break
        value = row[0]
        if value is None or not str(value).strip():
            break
        products.append(str(value).strip().upper())
    return _dedupe_products(products)


def _dedupe_products(products: Any) -> list[str]:
    normalized: list[str] = []
    for item in products:
        text = str(item or "").strip().upper()
        if not text:
            continue
        if COMBINED_PRODUCT_PATTERN.fullmatch(text):
            normalized.append(text)
        matches = PRODUCT_MODEL_PATTERN.findall(text)
        normalized.extend(match.upper() for match in matches)
    return list(dict.fromkeys(normalized))


def _allowed_product_set(products: list[str]) -> set[str]:
    return {product.strip().upper() for product in products if product.strip()}


def _product_matches_allowed(value: Any, allowed: set[str]) -> bool:
    product = str(value or "").strip().upper()
    if not product:
        return False
    if product in allowed:
        return True
    product_parts = set(PRODUCT_MODEL_PATTERN.findall(product))
    return bool(product_parts & allowed)


def _build_hl_candidates(
    hl_rows: list[dict[str, Any]],
    batch_yield_rows: list[dict[str, Any]],
    hl_history_rows: list[dict[str, Any]],
    *,
    product_models: list[str],
) -> list[dict[str, Any]]:
    df_hl = _frame(hl_rows)
    if df_hl.empty:
        return []
    df_yield = _frame(batch_yield_rows)
    df_hist = _frame(hl_history_rows)

    for column in ["ratio", "batch_ratio", "lag_ratio", "month_ratio", "ng_qty"]:
        if column in df_hl.columns:
            df_hl[column] = pd.to_numeric(df_hl[column], errors="coerce").fillna(0)

    if "batch_ratio" in df_hl.columns and "lag_ratio" in df_hl.columns:
        df_hl["batch_gap"] = df_hl["batch_ratio"] - df_hl["lag_ratio"]
    else:
        df_hl["batch_gap"] = 0.0

    if "month_ratio" in df_hl.columns and "batch_ratio" in df_hl.columns:
        df_hl["multiplier"] = df_hl.apply(
            lambda row: row["batch_ratio"] / row["month_ratio"]
            if row["month_ratio"] not in {0, None}
            else 0,
            axis=1,
        )
    else:
        df_hl["multiplier"] = 0.0

    if "interface_time" in df_hl.columns:
        df_hl["_dt"] = pd.to_datetime(df_hl["interface_time"], errors="coerce")
        df_hl = df_hl.sort_values("_dt", ascending=False)
        group_keys = ["prod_code", "defect_desc"]
        if "oper_group" in df_hl.columns:
            group_keys.append("oper_group")
        df_hl = df_hl.groupby(group_keys, as_index=False).first()
        df_hl = df_hl.drop(columns=["_dt"], errors="ignore")

    if not df_hist.empty:
        hist_time_col = "date_time" if "date_time" in df_hist.columns else "interface_time"
        if hist_time_col in df_hist.columns:
            df_hist["_dt_h"] = pd.to_datetime(df_hist[hist_time_col], errors="coerce")
            df_hist = df_hist.sort_values("_dt_h", ascending=False)
        cols_needed = ["prod_code", "defect_desc", "HL次数", "最新hl时间", "hl原因"]
        cols_exist = [column for column in cols_needed if column in df_hist.columns]
        if {"prod_code", "defect_desc"}.issubset(df_hist.columns) and cols_exist:
            df_hist_unique = df_hist.groupby(["prod_code", "defect_desc"], as_index=False).first()
            df_hl = pd.merge(
                df_hl,
                df_hist_unique[cols_exist],
                on=["prod_code", "defect_desc"],
                how="left",
            )

    if not df_yield.empty and {"prod_code", "batch"}.issubset(df_hl.columns):
        df_hl["_k1"] = df_hl["prod_code"].astype(str).str.strip()
        df_hl["_k2"] = df_hl["batch"].astype(str).str.strip()
        df_yield["_k1"] = df_yield["prod_code"].astype(str).str.strip()
        batch_column = "sub_prod_id" if "sub_prod_id" in df_yield.columns else "batch"
        if batch_column in df_yield.columns and "lot_input_ratio" in df_yield.columns:
            df_yield["_k2"] = df_yield[batch_column].astype(str).str.strip()
            df_yield = df_yield.groupby(["_k1", "_k2"], as_index=False).first()
            df_hl = pd.merge(
                df_hl,
                df_yield[["_k1", "_k2", "lot_input_ratio"]],
                on=["_k1", "_k2"],
                how="left",
            )
        df_hl = df_hl.drop(columns=["_k1", "_k2"], errors="ignore")

    if product_models and "prod_code" in df_hl.columns:
        allowed = _allowed_product_set(product_models)
        df_hl = df_hl[
            df_hl["prod_code"].map(lambda value: _product_matches_allowed(value, allowed))
        ]

    df_hl = _attach_occurrence_station(df_hl)
    records = df_hl.where(pd.notna(df_hl), None).to_dict("records")
    for index, record in enumerate(records, start=1):
        record.setdefault("row_id", f"hl-{index}")
        record["source_table"] = "hl_data"
    return records


def _build_mwdl_history(
    mwdl_rows: list[dict[str, Any]],
    defect_group_rows: list[dict[str, Any]],
    batch_yield_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    df_main = _frame(mwdl_rows)
    if df_main.empty:
        return []
    df_group = _frame(defect_group_rows)
    df_yield = _frame(batch_yield_rows)

    for column in ["ng_qty", "input_qty", "ratio"]:
        if column in df_main.columns:
            df_main[column] = pd.to_numeric(df_main[column], errors="coerce").fillna(0)

    if not df_group.empty and "defect_code" in df_main.columns and "defect_code" in df_group.columns:
        cols = [column for column in ["defect_code", "defect_group"] if column in df_group.columns]
        df_group_unique = df_group[cols].groupby("defect_code", as_index=False).first()
        df_main = pd.merge(df_main, df_group_unique, on="defect_code", how="left")

    if not df_yield.empty and "date_value" in df_main.columns and "prod_code" in df_main.columns:
        df_main["_k1"] = df_main["prod_code"].astype(str).str.strip()
        df_main["_k2"] = df_main["date_value"].astype(str).str.strip()
        df_yield["_k1"] = df_yield["prod_code"].astype(str).str.strip()
        batch_column = "sub_prod_id" if "sub_prod_id" in df_yield.columns else "batch"
        if batch_column in df_yield.columns and "lot_input_ratio" in df_yield.columns:
            df_yield["_k2"] = df_yield[batch_column].astype(str).str.strip()
            df_yield = df_yield.groupby(["_k1", "_k2"], as_index=False).first()
            df_main = pd.merge(
                df_main,
                df_yield[["_k1", "_k2", "lot_input_ratio"]],
                on=["_k1", "_k2"],
                how="left",
            )
        df_main = df_main.drop(columns=["_k1", "_k2"], errors="ignore")

    records = df_main.where(pd.notna(df_main), None).to_dict("records")
    for record in records:
        record["source_table"] = "mwdl_data"
    return records


def _build_mwdl_candidates(
    mwdl_rows: list[dict[str, Any]],
    batch_yield_rows: list[dict[str, Any]],
    *,
    existing_rows: list[dict[str, Any]],
    product_models: list[str],
) -> list[dict[str, Any]]:
    df = _frame(mwdl_rows)
    if df.empty or "date_type" not in df.columns:
        return []
    if product_models and "prod_code" in df.columns:
        allowed = _allowed_product_set(product_models)
        df = df[df["prod_code"].map(lambda value: _product_matches_allowed(value, allowed))].copy()
    if df.empty:
        return []

    for column in ["ng_qty", "input_qty", "ratio"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)
    df["_date_type"] = df["date_type"].astype(str).str.strip().str.upper()
    df["_prod_key"] = df["prod_code"].astype(str).str.strip().str.upper()
    df["_defect_key"] = df["defect_desc"].astype(str).str.strip()
    df["_station_key"] = df["oper_group"].astype(str).str.strip().str.upper()

    existing_keys = {
        (
            _first_text(row, "prod_code", "产品").upper(),
            _first_text(row, "defect_desc", "不良"),
            _first_text(row, "oper_group", "发生站点", "不良站点", "站点").upper(),
        )
        for row in existing_rows
    }
    df_yield = _frame(batch_yield_rows)
    yield_lookup: dict[tuple[str, str], float] = {}
    if not df_yield.empty and {"prod_code", "lot_input_ratio"}.issubset(df_yield.columns):
        batch_column = "sub_prod_id" if "sub_prod_id" in df_yield.columns else "batch"
        if batch_column in df_yield.columns:
            for _, item in df_yield.iterrows():
                key = (
                    str(item.get("prod_code") or "").strip().upper(),
                    str(item.get(batch_column) or "").strip(),
                )
                yield_lookup[key] = _to_float(item.get("lot_input_ratio"))

    summary_lookup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for _, item in df[df["_date_type"].isin(["DAY", "MONTH", "WEEK"])].iterrows():
        lookup_key = (
            str(item.get("_prod_key") or ""),
            str(item.get("_defect_key") or ""),
            str(item.get("_station_key") or ""),
            str(item.get("_date_type") or ""),
        )
        summary_lookup.setdefault(lookup_key, item.to_dict())

    selected_candidates: dict[tuple[str, str, str], dict[str, Any]] = {}
    lot_rows = df[(df["_date_type"] == "LOT") & (df["ratio"] > 0.001) & (df["ng_qty"] > 20)].copy()
    for _, lot_row in lot_rows.iterrows():
        prod = str(lot_row.get("_prod_key") or "").strip().upper()
        defect_desc = str(lot_row.get("_defect_key") or "").strip()
        station = str(lot_row.get("_station_key") or "").strip().upper()
        defect_code = str(lot_row.get("defect_code") or "").strip()
        batch = str(lot_row.get("date_value") or "").strip()
        key = (prod, defect_desc, station)
        if not prod or not defect_desc or not station or key in existing_keys:
            continue
        batch_ratio = _to_float(lot_row.get("ratio"))
        ng_qty = int(_to_float(lot_row.get("ng_qty")))
        lot_input_ratio = yield_lookup.get((prod, batch), 0.0)
        if batch_ratio <= 0.001 or ng_qty <= 20:
            continue

        lookup_key = (prod, defect_desc, station)
        day_row = summary_lookup.get((*lookup_key, "DAY"))
        if day_row is None:
            continue
        month_row = summary_lookup.get((*lookup_key, "MONTH"))
        week_row = summary_lookup.get((*lookup_key, "WEEK"))
        month_ratio = _to_float(month_row.get("ratio")) if month_row else 0.0
        multiplier = batch_ratio / month_ratio if month_ratio else 0.0
        candidate = {
            "row_id": "",
            "source_table": "mwdl_data",
            "prod_code": prod,
            "defect_desc": defect_desc,
            "defect_code": defect_code,
            "oper_group": station,
            "ratio": _to_float(day_row.get("ratio")),
            "month_ratio": month_ratio,
            "week_ratio": _to_float(week_row.get("ratio")) if week_row else 0.0,
            "batch_ratio": batch_ratio,
            "batch": batch,
            "lag_batch": "",
            "lag_ratio": 0.0,
            "batch_gap": batch_ratio,
            "lot_input_ratio": lot_input_ratio,
            "multiplier": multiplier,
            "ng_qty": ng_qty,
            "input_qty": _to_float(lot_row.get("input_qty")),
            "interface_time": _first_text(lot_row.to_dict(), "interface_time"),
            "occurrence_station": station,
        }
        current = selected_candidates.get(key)
        if current is None or (batch_ratio, ng_qty) > (
            _to_float(current.get("batch_ratio")),
            int(_to_float(current.get("ng_qty"))),
        ):
            selected_candidates[key] = candidate
    candidates = list(selected_candidates.values())
    for index, candidate in enumerate(candidates, start=1):
        candidate["row_id"] = f"mwdl-candidate-{index}"
    return candidates


def _build_ct_yield_detail(ct_yield_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = _frame(ct_yield_rows)
    if df.empty:
        return []
    if "ng_qty" in df.columns:
        df["ng_qty"] = pd.to_numeric(df["ng_qty"], errors="coerce").fillna(0)
        df = df[df["ng_qty"] > 0].copy()
    if "panel_id" in df.columns:
        df["panel_id"] = df["panel_id"].astype(str).replace("nan", "")
        valid = df["panel_id"].str.len() > 4
        df = df[valid].copy()
        df["row_code"] = df["panel_id"].str[-4:-2]
        df["col_code"] = df["panel_id"].str[-2:]
        df["membrane_pos"] = df["row_code"] + "-" + df["col_code"]
        df["行"] = df["row_code"]
        df["列"] = df["col_code"]
    records = df.where(pd.notna(df), None).to_dict("records")
    for record in records:
        record["source_table"] = "ct_yield_data"
    return records


def _attach_occurrence_station(df_hl: pd.DataFrame) -> pd.DataFrame:
    if df_hl.empty or not {"prod_code", "defect_desc", "oper_group"}.issubset(df_hl.columns):
        return df_hl
    occurrence: dict[tuple[str, str], str] = {}
    for _, item in df_hl.iterrows():
        station = str(item.get("oper_group") or "").strip().upper()
        if not station or station == "CT":
            continue
        key = (str(item.get("prod_code") or "").strip(), str(item.get("defect_desc") or "").strip())
        occurrence.setdefault(key, station)

    def resolve(row: pd.Series[Any]) -> str:
        station = str(row.get("oper_group") or "").strip().upper()
        if station != "CT":
            return station
        key = (str(row.get("prod_code") or "").strip(), str(row.get("defect_desc") or "").strip())
        return occurrence.get(key, station)

    df_hl["occurrence_station"] = df_hl.apply(resolve, axis=1)
    return df_hl


def _frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame.columns = [str(column).strip() for column in frame.columns]
    for column in frame.columns:
        if pd.api.types.is_object_dtype(frame[column]) or pd.api.types.is_string_dtype(frame[column]):
            frame[column] = frame[column].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )
    return frame


def _first_row(frame: pd.DataFrame, date_type: str) -> dict[str, Any] | None:
    matches = frame[frame["_date_type"] == date_type]
    if matches.empty:
        return None
    return matches.iloc[0].to_dict()


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        number = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return 0.0
    if pd.isna(number):
        return 0.0
    return number


def _normalize_ct_exception_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if row.get("source_table") == "ct_exception":
            normalized.append(dict(row))
            continue
        if not _looks_like_ct_exception_row(row):
            normalized.append(dict(row))
            continue
        interface_time = _first_text(row, "\u901a\u62a5\u65e5\u671f", "interface_time")
        report_date = _date_part(interface_time)
        notice_text = _first_text(row, "\u5f02\u5e38\u901a\u62a5", "notice_text")
        normalized.append(
            {
                "row_id": f"ct-exception-{index + 1}",
                "source_table": "ct_exception",
                "prod_code": _first_text(row, "\u4ea7\u54c1", "prod_code"),
                "defect_desc": _first_text(row, "\u4e0d\u826f", "defect_desc"),
                "defect_code": _first_text(row, "defect_code"),
                "oper_group": _first_text(row, "\u4e0d\u826f\u7ad9\u70b9", "oper_group").upper(),
                "ratio": _first_value(row, "\u65e5\u826f\u635f", "ratio"),
                "month_ratio": _first_value(row, "\u5f53\u6708", "month_ratio"),
                "week_ratio": _first_value(row, "\u5f53\u5468", "week_ratio"),
                "batch_ratio": _first_value(row, "\u672c\u6279\u6b21", "batch_ratio"),
                "batch": _first_text(row, "batch", "date_value") or report_date,
                "batch_date": report_date,
                "date_value": report_date,
                "interface_time": interface_time,
                "lot_input_ratio": 1.0,
                "lot_input_ratio_source": "ct_exception",
                "owner": _first_text(row, "\u5f02\u5e38\u5bf9\u63a5\u4eba", "owner"),
                "status": _first_text(row, "\u72b6\u6001", "status"),
                "concentration_text": _extract_concentration_text(row, notice_text),
                "notice_text": notice_text,
                "raw_ct_exception": row,
            }
        )
    return normalized


def _filter_product_models(
    rows: list[dict[str, Any]],
    product_models: list[str],
) -> list[dict[str, Any]]:
    if not product_models:
        return rows
    allowed = _allowed_product_set(product_models)
    return [
        row
        for row in rows
        if _product_matches_allowed(_first_text(row, "prod_code", "\u4ea7\u54c1"), allowed)
    ]


def _looks_like_ct_exception_row(row: dict[str, Any]) -> bool:
    return "\u901a\u62a5\u65e5\u671f" in row and "\u4ea7\u54c1" in row and "\u4e0d\u826f" in row


def _extract_concentration_text(row: dict[str, Any], notice_text: str) -> str:
    parts = [
        notice_text,
        _first_text(row, "\u56fa\u5b9a\u819c\u4f4d"),
        _first_text(row, "\u5f02\u5e38\u7ad9\u70b9/\u5e73\u53f0/\u8154\u5ba4"),
    ]
    return "\n".join(part for part in parts if part)


def _date_part(value: Any) -> str:
    parsed = _parse_date(str(value or ""))
    return parsed.isoformat() if parsed is not None else ""


def _parse_date(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("/", "-")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        year, month, day = (int(item) for item in match.groups())
        return date(year, month, day)
    return None


def _first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def _first_text(row: dict[str, Any], *keys: str) -> str:
    value = _first_value(row, *keys)
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value)).strip()
    return str(value).strip()
