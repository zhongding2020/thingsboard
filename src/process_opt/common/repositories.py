import json
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
                INSERT INTO process_summary (barcode, device_id, processed_at, params, product_model)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (barcode) DO UPDATE SET
                  device_id = EXCLUDED.device_id,
                  processed_at = EXCLUDED.processed_at,
                  params = EXCLUDED.params,
                  product_model = EXCLUDED.product_model,
                  updated_at = now()
                """,
                message.barcode,
                message.device_id,
                message.processed_at,
                message.params,
                message.product_model,
            )

    async def upsert_inspection(self, message: InspectionMessage) -> None:
        async with self._pool.acquire() as connection:
            results_json = [item.model_dump() for item in message.results]
            await connection.execute(
                """
                INSERT INTO inspection_results (barcode, station_id, inspected_at, results, product_model)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                ON CONFLICT (barcode) DO UPDATE SET
                  station_id = EXCLUDED.station_id,
                  inspected_at = EXCLUDED.inspected_at,
                  results = EXCLUDED.results,
                  product_model = EXCLUDED.product_model,
                  updated_at = now()
                """,
                message.barcode,
                message.station_id,
                message.inspected_at,
                json.dumps(results_json),
                message.product_model,
            )

    async def get_analysis_record(self, barcode: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT barcode, device_id, processed_at, params,
                       station_id, inspected_at, results,
                       process_product_model, inspection_product_model
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
        station_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        product_model: str | None = None,
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
        if station_id is not None:
            conditions.append(f"station_id = ${len(params) + 1}")
            params.append(station_id)
        if start_time is not None:
            conditions.append(f"processed_at >= ${len(params) + 1}")
            params.append(start_time)
        if end_time is not None:
            conditions.append(f"processed_at <= ${len(params) + 1}")
            params.append(end_time)
        if product_model is not None:
            conditions.append(f"(process_product_model = ${len(params) + 1} OR inspection_product_model = ${len(params) + 2})")
            params.append(product_model)
            params.append(product_model)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        offset = (page - 1) * page_size

        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                f"""
                SELECT barcode, device_id, processed_at, params,
                       station_id, inspected_at, results,
                       process_product_model, inspection_product_model,
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
                "process_product_model": r["process_product_model"],
                "inspection_product_model": r["inspection_product_model"],
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


class LineDeviceRepository:
    """Repository for production_lines and device_registry tables."""

    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def list_lines(self) -> list[dict[str, Any]]:
        async with self._pool.acquire() as connection:
            rows = await connection.fetch("""
                SELECT l.id, l.name, l.responsible, l.location,
                       l.created_at, l.updated_at,
                       COUNT(d.id) AS device_count
                FROM production_lines l
                LEFT JOIN device_registry d ON d.line_id = l.id
                GROUP BY l.id
                ORDER BY l.name
            """)
        return [dict(r) for r in rows]

    async def get_line(self, line_id: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow("""
                SELECT l.id, l.name, l.responsible, l.location,
                       l.created_at, l.updated_at,
                       COUNT(d.id) AS device_count
                FROM production_lines l
                LEFT JOIN device_registry d ON d.line_id = l.id
                WHERE l.id = $1
                GROUP BY l.id
            """, line_id)
        return dict(row) if row else None

    async def create_line(self, name: str, responsible: str, location: str | None) -> dict[str, Any]:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow("""
                INSERT INTO production_lines (name, responsible, location)
                VALUES ($1, $2, $3)
                RETURNING id, name, responsible, location, created_at, updated_at
            """, name, responsible, location)
        result = dict(row)
        result["device_count"] = 0
        return result

    async def update_line(self, line_id: str, name: str | None,
                          responsible: str | None, location: str | None) -> dict[str, Any] | None:
        fields: list[str] = []
        params: list[Any] = [line_id]
        idx = 2
        if name is not None:
            fields.append(f"name = ${idx}")
            params.append(name)
            idx += 1
        if responsible is not None:
            fields.append(f"responsible = ${idx}")
            params.append(responsible)
            idx += 1
        if location is not None:
            fields.append(f"location = ${idx}")
            params.append(location)
            idx += 1
        if not fields:
            return await self.get_line(line_id)
        fields.append("updated_at = now()")
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(f"""
                UPDATE production_lines
                SET {', '.join(fields)}
                WHERE id = $1
                RETURNING id, name, responsible, location, created_at, updated_at
            """, *params)
        if row is None:
            return None
        result = await self.get_line(line_id)
        return result

    async def delete_line(self, line_id: str) -> bool:
        async with self._pool.acquire() as connection:
            device_count = await connection.fetchval(
                "SELECT COUNT(*) FROM device_registry WHERE line_id = $1", line_id
            )
            if device_count and device_count > 0:
                return False
            result = await connection.execute(
                "DELETE FROM production_lines WHERE id = $1", line_id
            )
        return result != "DELETE 0"

    async def list_devices(self, line_id: str | None = None) -> list[dict[str, Any]]:
        async with self._pool.acquire() as connection:
            if line_id is not None:
                rows = await connection.fetch("""
                    SELECT d.id, d.line_id, l.name AS line_name,
                           d.name, d.type, d.icon, d.description, d.sort_order
                    FROM device_registry d
                    LEFT JOIN production_lines l ON l.id = d.line_id
                    WHERE d.line_id = $1
                    ORDER BY d.sort_order, d.name
                """, line_id)
            else:
                rows = await connection.fetch("""
                    SELECT d.id, d.line_id, l.name AS line_name,
                           d.name, d.type, d.icon, d.description, d.sort_order
                    FROM device_registry d
                    LEFT JOIN production_lines l ON l.id = d.line_id
                    ORDER BY d.sort_order, d.name
                """)
        return [dict(r) for r in rows]

    async def get_device(self, device_id: str) -> dict[str, Any] | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow("""
                SELECT d.id, d.line_id, l.name AS line_name,
                       d.name, d.type, d.icon, d.description
                FROM device_registry d
                LEFT JOIN production_lines l ON l.id = d.line_id
                WHERE d.id = $1
            """, device_id)
        return dict(row) if row else None

    async def update_device(self, device_id: str, name: str | None, type_: str | None,
                            icon: str | None, description: str | None,
                            line_id: str | None) -> dict[str, Any] | None:
        fields: list[str] = []
        params: list[Any] = [device_id]
        idx = 2
        if name is not None:
            fields.append(f"name = ${idx}")
            params.append(name)
            idx += 1
        if type_ is not None:
            fields.append(f"type = ${idx}")
            params.append(type_)
            idx += 1
        if icon is not None:
            fields.append(f"icon = ${idx}")
            params.append(icon)
            idx += 1
        if description is not None:
            fields.append(f"description = ${idx}")
            params.append(description)
            idx += 1
        if line_id is not None:
            fields.append(f"line_id = ${idx}")
            params.append(line_id)
            idx += 1
        if not fields:
            return await self.get_device(device_id)
        fields.append("updated_at = now()")
        async with self._pool.acquire() as connection:
            await connection.execute(f"""
                UPDATE device_registry SET {', '.join(fields)} WHERE id = $1
            """, *params)
        return await self.get_device(device_id)

    async def delete_device(self, device_id: str) -> bool:
        async with self._pool.acquire() as connection:
            result = await connection.execute(
                "DELETE FROM device_registry WHERE id = $1", device_id
            )
        return result != "DELETE 0"

    async def get_devices_by_line(self, line_id: str) -> list[str]:
        """Return device IDs for a line. Used by SPC filtering."""
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                "SELECT id FROM device_registry WHERE line_id = $1 ORDER BY id",
                line_id,
            )
        return [r["id"] for r in rows]

    async def reorder_devices(self, line_id: str, device_ids: list[str]) -> None:
        """Update sort_order for devices in a line based on the ordered list."""
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                for idx, device_id in enumerate(device_ids):
                    await connection.execute(
                        "UPDATE device_registry SET sort_order = $1, updated_at = now() WHERE id = $2 AND line_id = $3",
                        idx, device_id, line_id,
                    )

    async def ensure_device_exists(
        self, device_id: str, device_type: str,
        line_id: str | None = None, name: str | None = None,
    ) -> None:
        """Idempotent device registration for mock generator.

        Resolves line_id by id first, then by name, then falls back to 默认产线.
        """
        device_name = name or device_id
        async with self._pool.acquire() as connection:
            resolved_line_id: str | None = None

            if line_id:
                # Try as UUID first
                try:
                    resolved_line_id = await connection.fetchval(
                        "SELECT id FROM production_lines WHERE id = $1::uuid",
                        line_id,
                    )
                except Exception:
                    resolved_line_id = None

                # If not found by UUID, try by name
                if resolved_line_id is None:
                    resolved_line_id = await connection.fetchval(
                        "SELECT id FROM production_lines WHERE name = $1",
                        line_id,
                    )

            # Fallback to 默认产线
            if resolved_line_id is None:
                resolved_line_id = await connection.fetchval(
                    "SELECT id FROM production_lines WHERE name = '默认产线' LIMIT 1"
                )

            await connection.execute("""
                INSERT INTO device_registry (id, line_id, name, type, icon, description)
                VALUES ($1, $2, $3, $4, 'Monitor', '自动注册')
                ON CONFLICT (id) DO NOTHING
            """, device_id, resolved_line_id, device_name, device_type)
