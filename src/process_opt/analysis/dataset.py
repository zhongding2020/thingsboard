from __future__ import annotations

from datetime import datetime
from statistics import mean, median
from typing import Any

import asyncpg

from process_opt.analysis.errors import AnalysisError
from process_opt.analysis.schemas import AnalysisDataset, AnalysisDatasetRequest


def _stat(values: list[float], strategy: str) -> float:
    if strategy == "mean":
        return mean(values)
    return median(values)


class DatasetBuilder:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def build(
        self, request: AnalysisDatasetRequest,
        device_id: str | None = None,
        since: datetime | None = None,
    ) -> AnalysisDataset | AnalysisError:
        query = "SELECT * FROM analysis_view"
        conditions: list[str] = []
        params: list[Any] = []
        idx = 0

        if device_id is not None:
            idx += 1
            conditions.append(f"device_id = ${idx}")
            params.append(device_id)
        if since is not None:
            idx += 1
            conditions.append(f"processed_at >= ${idx}")
            params.append(since)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY barcode"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        if not rows:
            return AnalysisError(
                code="INSUFFICIENT_SAMPLES",
                message="No samples found in database",
                suggestion="Ensure data has been ingested before analysis",
            )

        all_param_keys: set[str] = set()
        all_result_keys: set[str] = set()
        for row in rows:
            if row["params"] is not None:
                all_param_keys.update(row["params"].keys())
            if row["results"] is not None:
                all_result_keys.update(row["results"].keys())

        for field in request.feature_fields:
            if field not in all_param_keys:
                return AnalysisError(
                    code="FIELD_NOT_FOUND",
                    message=f"Feature field '{field}' not found in params data",
                    suggestion=f"Available param keys: {sorted(all_param_keys)}",
                )
        for field in request.target_fields:
            if field not in all_result_keys:
                return AnalysisError(
                    code="FIELD_NOT_FOUND",
                    message=f"Target field '{field}' not found in results data",
                    suggestion=f"Available result keys: {sorted(all_result_keys)}",
                )

        use_feature_fields = request.feature_fields or list(all_param_keys)
        use_target_fields = request.target_fields or list(all_result_keys)
        all_fields = use_feature_fields + use_target_fields
        features: list[dict[str, Any]] = []
        targets: list[dict[str, Any]] = []
        metadata: list[dict[str, Any]] = []

        for row in rows:
            feat = {}
            if row["params"] is not None:
                for f in use_feature_fields:
                    if f in row["params"]:
                        feat[f] = row["params"][f]
            features.append(feat)

            tgt = {}
            if row["results"] is not None:
                for t in use_target_fields:
                    if t in row["results"]:
                        tgt[t] = row["results"][t]
            targets.append(tgt)

            metadata.append({
                "barcode": row["barcode"],
                "device_id": row["device_id"],
                "station_id": row["station_id"],
                "processed_at": row["processed_at"].isoformat() if row["processed_at"] else None,
                "inspected_at": row["inspected_at"].isoformat() if row["inspected_at"] else None,
            })

        features, targets, metadata = self._handle_missing(
            features, targets, metadata, request, use_feature_fields, use_target_fields,
        )

        if not features:
            return AnalysisError(
                code="INSUFFICIENT_SAMPLES",
                message="After applying missing value strategy, no samples remain",
                suggestion="Try a different missing strategy or include more data",
            )

        truncated = False
        if request.max_samples is not None and len(features) > request.max_samples:
            features = features[: request.max_samples]
            targets = targets[: request.max_samples]
            metadata = metadata[: request.max_samples]
            truncated = True

        field_summary: dict[str, Any] = {}
        for field in all_fields:
            values = []
            for feat in features:
                if field in feat and feat[field] is not None:
                    values.append(feat[field])
            for tgt in targets:
                if field in tgt and tgt[field] is not None:
                    values.append(tgt[field])
            numeric = [v for v in values if isinstance(v, (int, float))]
            field_summary[field] = {
                "count": len(values),
                "numeric_count": len(numeric),
            }
            if numeric:
                field_summary[field].update({
                    "mean": mean(numeric),
                    "min": min(numeric),
                    "max": max(numeric),
                })

        return AnalysisDataset(
            features=features,
            targets=targets,
            metadata=metadata,
            field_summary=field_summary,
            sample_count=len(features),
            truncated=truncated,
        )

    def _handle_missing(
        self,
        features: list[dict[str, Any]],
        targets: list[dict[str, Any]],
        metadata: list[dict[str, Any]],
        request: AnalysisDatasetRequest,
        use_feature_fields: list[str] | None = None,
        use_target_fields: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        strategy = request.missing_strategy
        if strategy == "drop_row":
            return self._drop_row(features, targets, metadata, request, use_feature_fields, use_target_fields)

        all_fields = (use_feature_fields or request.feature_fields) + (use_target_fields or request.target_fields)
        fill_values: dict[str, float] = {}
        for field in all_fields:
            existing = []
            for feat in features:
                if field in feat and isinstance(feat[field], (int, float)):
                    existing.append(feat[field])
            for tgt in targets:
                if field in tgt and isinstance(tgt[field], (int, float)):
                    existing.append(tgt[field])
            if existing:
                fill_values[field] = _stat(existing, strategy)

        for i in range(len(features)):
            for f in request.feature_fields:
                if f not in features[i] and f in fill_values:
                    features[i][f] = fill_values[f]
            for t in request.target_fields:
                if t not in targets[i] and t in fill_values:
                    targets[i][t] = fill_values[t]

        return features, targets, metadata

    def _drop_row(
        self,
        features: list[dict[str, Any]],
        targets: list[dict[str, Any]],
        metadata: list[dict[str, Any]],
        request: AnalysisDatasetRequest,
        use_feature_fields: list[str] | None = None,
        use_target_fields: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        ff = use_feature_fields or request.feature_fields
        tf = use_target_fields or request.target_fields
        valid: list[int] = []
        for i in range(len(features)):
            feat_ok = all(
                f in features[i] and features[i][f] is not None
                for f in ff
            )
            tgt_ok = all(
                t in targets[i] and targets[i][t] is not None
                for t in tf
            )
            if feat_ok and tgt_ok:
                valid.append(i)

        return (
            [features[i] for i in valid],
            [targets[i] for i in valid],
            [metadata[i] for i in valid],
        )
