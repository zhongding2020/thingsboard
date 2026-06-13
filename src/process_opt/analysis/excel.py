from __future__ import annotations

import time
from io import BytesIO
from uuid import uuid4

import openpyxl

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset

_DEFAULT_TTL = 1800
_store: dict[str, AnalysisDataset] = {}
_expiry: dict[str, float] = {}


def _uuid() -> str:
    return uuid4().hex


def _purge_expired() -> None:
    now = time.monotonic()
    expired = [k for k, t in _expiry.items() if now >= t]
    for k in expired:
        _store.pop(k, None)
        _expiry.pop(k, None)


def save_dataset(dataset: AnalysisDataset, ttl: int = _DEFAULT_TTL) -> str:
    _purge_expired()
    key = _uuid()
    _store[key] = dataset
    _expiry[key] = time.monotonic() + ttl
    return key


def get_dataset(key: str) -> AnalysisDataset | None:
    _purge_expired()
    return _store.get(key)


def parse_excel(file_bytes: bytes) -> AnalysisDataset:
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb.active
    if ws is None:
        raise AnalysisError(code="EMPTY_FILE", message="Excel file is empty")

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        raise AnalysisError(
            code="EMPTY_FILE",
            message="Excel must have at least a header row and one data row",
        )

    headers = [str(h).strip() for h in rows[0] if h is not None]
    if not headers:
        raise AnalysisError(code="EMPTY_FILE", message="No headers found")

    features: list[dict[str, float | None]] = []
    targets: list[dict[str, str | None]] = []
    metadata: list[dict[str, str]] = []

    feature_cols: list[int] = []
    target_cols: list[int] = []

    for i, h in enumerate(headers):
        for row in rows[1:]:
            v = row[i] if i < len(row) else None
            if v is not None and isinstance(v, (int, float)):
                feature_cols.append(i)
                break
            if v is not None and isinstance(v, str) and v.strip():
                if v.strip().lower() in ("pass", "fail"):
                    target_cols.append(i)
                break
        else:
            feature_cols.append(i)

    target_cols = [i for i in range(len(headers)) if i not in feature_cols]

    for r, row in enumerate(rows[1:]):
        feat: dict[str, float | None] = {}
        tgt: dict[str, str | None] = {}
        for i in feature_cols:
            name = headers[i]
            v = row[i] if i < len(row) else None
            if isinstance(v, (int, float)):
                feat[name] = float(v)
            elif isinstance(v, str) and v.strip():
                try:
                    feat[name] = float(v.strip())
                except ValueError:
                    feat[name] = None
            else:
                feat[name] = None

        for i in target_cols:
            name = headers[i]
            v = row[i] if i < len(row) else None
            if isinstance(v, str):
                tgt[name] = v.strip().lower()
            else:
                tgt[name] = str(v).strip().lower() if v is not None else None

        features.append(feat)
        targets.append(tgt)
        metadata.append({"barcode": f"excel-{r+1}", "processed_at": ""})

    return AnalysisDataset(
        features=features,
        targets=targets,
        metadata=metadata,
        field_summary={},
        sample_count=len(features),
    )
