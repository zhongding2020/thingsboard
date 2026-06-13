from typing import Any

from process_opt.common.db import Pool
from process_opt.parameters.schemas import ParameterItem, ParameterSet, ParameterSetCreate, ParameterStatus


class ParameterRepository:
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def create_set(self, parameter_set: ParameterSetCreate) -> ParameterSet:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                version = await connection.fetchval(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1
                    FROM parameter_sets
                    WHERE device_type = $1
                    """,
                    parameter_set.device_type,
                )
                row = await connection.fetchrow(
                    """
                    INSERT INTO parameter_sets (name, device_type, version, status, source, created_by, note)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id, name, device_type, version, status, source, created_by, approved_by,
                      activated_by, note, created_at, updated_at, approved_at, activated_at, archived_at
                    """,
                    parameter_set.name,
                    parameter_set.device_type,
                    version,
                    ParameterStatus.DRAFT.value,
                    parameter_set.source,
                    parameter_set.created_by,
                    parameter_set.note,
                )
                for item in parameter_set.items:
                    await connection.execute(
                        """
                        INSERT INTO parameter_items (
                          set_id, param_key, param_value, unit, data_type, min_value, max_value, description
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """,
                        row["id"],
                        item.param_key,
                        item.param_value,
                        item.unit,
                        item.data_type,
                        item.min_value,
                        item.max_value,
                        item.description,
                    )
        return self._set_from_row(row)

    async def get_set(self, set_id: int) -> ParameterSet | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT id, name, device_type, version, status, source, created_by, approved_by,
                  activated_by, note, created_at, updated_at, approved_at, activated_at, archived_at
                FROM parameter_sets
                WHERE id = $1
                """,
                set_id,
            )
        if row is None:
            return None
        return self._set_from_row(row)

    async def list_items(self, set_id: int) -> list[ParameterItem]:
        async with self._pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT id, set_id, param_key, param_value, unit, data_type, min_value, max_value, description
                FROM parameter_items
                WHERE set_id = $1
                ORDER BY id
                """,
                set_id,
            )
        return [self._item_from_row(row) for row in rows]

    async def add_event(self, set_id: int, event_type: str, actor: str, note: str | None = None) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO parameter_set_events (set_id, event_type, actor, note)
                VALUES ($1, $2, $3, $4)
                """,
                set_id,
                event_type,
                actor,
                note,
            )

    async def update_status(
        self,
        set_id: int,
        status: ParameterStatus,
        actor: str,
        note: str | None = None,
    ) -> ParameterSet | None:
        assignments = {
            ParameterStatus.APPROVED: "approved_by = $3, approved_at = now(),",
            ParameterStatus.ACTIVE: "activated_by = $3, activated_at = now(),",
            ParameterStatus.ARCHIVED: "archived_at = now(),",
        }
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                sql = f"""
                    UPDATE parameter_sets
                    SET status = $2,
                      {assignments.get(status, "")}
                      updated_at = now()
                    WHERE id = $1
                    RETURNING id, name, device_type, version, status, source, created_by, approved_by,
                      activated_by, note, created_at, updated_at, approved_at, activated_at, archived_at
                """
                args: list[Any] = [set_id, status.value]
                if status in {ParameterStatus.APPROVED, ParameterStatus.ACTIVE}:
                    args.append(actor)
                row = await connection.fetchrow(sql, *args)
                if row is None:
                    return None
                await connection.execute(
                    """
                    INSERT INTO parameter_set_events (set_id, event_type, actor, note)
                    VALUES ($1, $2, $3, $4)
                    """,
                    set_id,
                    self._event_type_for_status(status),
                    actor,
                    note,
                )
        return self._set_from_row(row)

    async def get_latest_active(self, device_type: str) -> ParameterSet | None:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT id, name, device_type, version, status, source, created_by, approved_by,
                  activated_by, note, created_at, updated_at, approved_at, activated_at, archived_at
                FROM parameter_sets
                WHERE device_type = $1 AND status = $2
                ORDER BY version DESC
                LIMIT 1
                """,
                device_type,
                ParameterStatus.ACTIVE.value,
            )
        if row is None:
            return None
        return self._set_from_row(row)

    async def insert_confirmation(
        self,
        device_id: str,
        device_type: str,
        parameter_set_id: int,
        parameter_version: int,
        status: str,
        message: str | None = None,
    ) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO parameter_confirmations (
                  device_id, device_type, parameter_set_id, parameter_version, status, message
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                device_id,
                device_type,
                parameter_set_id,
                parameter_version,
                status,
                message,
            )

    async def replace_with_active(
        self,
        set_id: int,
        old_active_id: int | None,
        actor: str,
        note: str | None = None,
    ) -> ParameterSet:
        async with self._pool.acquire() as connection:
            async with connection.transaction():
                if old_active_id is not None:
                    await connection.execute(
                        """
                        UPDATE parameter_sets
                        SET status = $1, updated_at = now(), archived_at = now()
                        WHERE id = $2
                        """,
                        ParameterStatus.ARCHIVED.value,
                        old_active_id,
                    )
                    await connection.execute(
                        """
                        INSERT INTO parameter_set_events (set_id, event_type, actor)
                        VALUES ($1, $2, $3)
                        """,
                        old_active_id,
                        "archive",
                        actor,
                    )
                row = await connection.fetchrow(
                    """
                    UPDATE parameter_sets
                    SET status = $1,
                      activated_by = $2,
                      activated_at = now(),
                      updated_at = now()
                    WHERE id = $3
                    RETURNING id, name, device_type, version, status, source, created_by, approved_by,
                      activated_by, note, created_at, updated_at, approved_at, activated_at, archived_at
                    """,
                    ParameterStatus.ACTIVE.value,
                    actor,
                    set_id,
                )
                await connection.execute(
                    """
                    INSERT INTO parameter_set_events (set_id, event_type, actor, note)
                    VALUES ($1, $2, $3, $4)
                    """,
                    set_id,
                    "activate",
                    actor,
                    note,
                )
        return self._set_from_row(row)

    async def next_version(self, device_type: str) -> int:
        async with self._pool.acquire() as connection:
            version = await connection.fetchval(
                """
                SELECT COALESCE(MAX(version), 0) + 1
                FROM parameter_sets
                WHERE device_type = $1
                """,
                device_type,
            )
        return int(version)

    def _set_from_row(self, row: Any) -> ParameterSet:
        return ParameterSet(
            id=row["id"],
            name=row["name"],
            device_type=row["device_type"],
            version=row["version"],
            status=ParameterStatus(row["status"]),
            source=row["source"],
            created_by=row["created_by"],
            approved_by=row["approved_by"],
            activated_by=row["activated_by"],
            note=row["note"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            approved_at=row["approved_at"],
            activated_at=row["activated_at"],
            archived_at=row["archived_at"],
        )

    def _item_from_row(self, row: Any) -> ParameterItem:
        return ParameterItem(
            id=row["id"],
            set_id=row["set_id"],
            param_key=row["param_key"],
            param_value=row["param_value"],
            unit=row["unit"],
            data_type=row["data_type"],
            min_value=row["min_value"],
            max_value=row["max_value"],
            description=row["description"],
        )

    def _event_type_for_status(self, status: ParameterStatus) -> str:
        return {
            ParameterStatus.PROPOSED: "submit",
            ParameterStatus.APPROVED: "approve",
            ParameterStatus.REJECTED: "reject",
            ParameterStatus.ACTIVE: "activate",
            ParameterStatus.ARCHIVED: "archive",
        }.get(status, status.value)
