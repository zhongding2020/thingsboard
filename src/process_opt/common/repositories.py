from datetime import datetime
from typing import Any

from process_opt.common.db import Pool
from process_opt.common.schemas import InspectionMessage, ProcessMessage


class DataRepository:
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def upsert_process(self, message: ProcessMessage) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO process_summary (barcode, device_id, processed_at, params)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (barcode) DO UPDATE SET
                  device_id = EXCLUDED.device_id,
                  processed_at = EXCLUDED.processed_at,
                  params = EXCLUDED.params,
                  updated_at = now()
                """,
                message.barcode,
                message.device_id,
                message.processed_at,
                message.params,
            )

    async def upsert_inspection(self, message: InspectionMessage) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO inspection_results (barcode, station_id, inspected_at, results)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (barcode) DO UPDATE SET
                  station_id = EXCLUDED.station_id,
                  inspected_at = EXCLUDED.inspected_at,
                  results = EXCLUDED.results,
                  updated_at = now()
                """,
                message.barcode,
                message.station_id,
                message.inspected_at,
                message.results,
            )

    async def get_analysis_record(self, barcode: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT barcode, device_id, processed_at, params, station_id, inspected_at, results
                FROM analysis_view
                WHERE barcode = $1
                """,
                barcode,
            )
        if row is None:
            return None
        return dict(row)

    async def query_records(
        self,
        barcode: str | None = None,
        device_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20
        if page_size > 100:
            page_size = 100

        conditions: list[str] = []
        params: list[Any] = []

        if barcode is not None:
            conditions.append(f"barcode = ${len(params) + 1}")
            params.append(barcode)
        if device_id is not None:
            conditions.append(f"device_id = ${len(params) + 1}")
            params.append(device_id)
        if start_time is not None:
            conditions.append(f"processed_at >= ${len(params) + 1}")
            params.append(start_time)
        if end_time is not None:
            conditions.append(f"processed_at <= ${len(params) + 1}")
            params.append(end_time)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        offset = (page - 1) * page_size

        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                f"""
                SELECT barcode, device_id, processed_at, params,
                       station_id, inspected_at, results,
                       COUNT(*) OVER() AS total_count
                FROM analysis_view
                WHERE {where_clause}
                ORDER BY processed_at DESC
                OFFSET ${len(params) + 1} LIMIT ${len(params) + 2}
                """,
                *params,
                offset,
                page_size,
            )

        if not rows:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

        total = rows[0]["total_count"]
        items = [
            {
                "barcode": r["barcode"],
                "device_id": r["device_id"],
                "processed_at": r["processed_at"],
                "params": r["params"],
                "station_id": r["station_id"],
                "inspected_at": r["inspected_at"],
                "results": r["results"],
            }
            for r in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def list_devices(self) -> list[str]:
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT DISTINCT device_id FROM process_summary ORDER BY device_id"
            )
        return [r["device_id"] for r in rows]

    async def get_stats(self) -> dict[str, Any]:
        async with self._pool.acquire() as connection:
            today = await connection.fetchval(
                "SELECT COUNT(*) FROM process_summary WHERE processed_at >= CURRENT_DATE"
            )
            total = await connection.fetchval("SELECT COUNT(*) FROM process_summary")
            devices_row = await connection.fetchval(
                "SELECT COUNT(DISTINCT device_id) FROM process_summary"
            )
            pending = await connection.fetchval(
                "SELECT COUNT(*) FROM parameter_sets WHERE status = 'proposed'"
            )
            recent_rows = await connection.fetch(
                """
                SELECT barcode, device_id, processed_at FROM process_summary
                ORDER BY processed_at DESC LIMIT 5
                """
            )
        return {
            "today_data_count": today or 0,
            "total_records": total or 0,
            "device_count": devices_row or 0,
            "pending_approvals": pending or 0,
            "latest_records": [
                {"barcode": r["barcode"], "device_id": r["device_id"], "processed_at": r["processed_at"].isoformat()}
                for r in recent_rows
            ],
        }
