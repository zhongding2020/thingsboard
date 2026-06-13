from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from process_opt.api.main import create_api_app_from_settings
from process_opt.common.db import apply_sql_file


@pytest.mark.asyncio
async def test_parameter_full_lifecycle() -> None:
    migration_path = Path(__file__).parents[2] / "db" / "migrations" / "001_initial.sql"

    app = create_api_app_from_settings()

    async with app.router.lifespan_context(app):
        pool = app.state.pool
        await apply_sql_file(pool, migration_path)
        async with pool.acquire() as conn:
            for table in ["parameter_confirmations", "parameter_set_events", "parameter_items", "parameter_sets"]:
                await conn.execute(f"DELETE FROM {table}")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # --- create draft ---
            create_payload = {
                "name": "Line A defaults",
                "device_type": "soldering-oven",
                "source": "engineering",
                "created_by": "alice",
                "note": "initial rollout",
                "items": [
                    {
                        "param_key": "temperature",
                        "param_value": 180,
                        "unit": "C",
                        "data_type": "number",
                        "min_value": 150,
                        "max_value": 220,
                        "description": "Peak temperature",
                    },
                    {
                        "param_key": "profile",
                        "param_value": {"ramp": "slow"},
                        "data_type": "object",
                    },
                ],
            }
            response = await client.post("/api/v1/parameters/sets", json=create_payload)
            assert response.status_code == 201
            set_id = response.json()["id"]
            assert response.json()["status"] == "draft"

            # --- submit draft -> proposed ---
            response = await client.post(f"/api/v1/parameters/sets/{set_id}/submit", json={"actor": "alice"})
            assert response.status_code == 200
            assert response.json()["status"] == "proposed"

            # --- approve proposed -> approved ---
            response = await client.post(f"/api/v1/parameters/sets/{set_id}/approve", json={"actor": "bob"})
            assert response.status_code == 200
            assert response.json()["status"] == "approved"

            # --- activate approved -> active ---
            response = await client.post(f"/api/v1/parameters/sets/{set_id}/activate", json={"actor": "carol"})
            assert response.status_code == 200
            assert response.json()["status"] == "active"

            # --- create second set, activate -> verify old active archived ---
            create_payload2 = dict(create_payload, name="Line A v2", note="second version")
            response = await client.post("/api/v1/parameters/sets", json=create_payload2)
            assert response.status_code == 201
            set_id2 = response.json()["id"]

            await client.post(f"/api/v1/parameters/sets/{set_id2}/submit", json={"actor": "alice"})
            await client.post(f"/api/v1/parameters/sets/{set_id2}/approve", json={"actor": "bob"})
            response = await client.post(f"/api/v1/parameters/sets/{set_id2}/activate", json={"actor": "carol"})
            assert response.status_code == 200
            assert response.json()["status"] == "active"

            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT status FROM parameter_sets WHERE id = $1", set_id)
            assert row["status"] == "archived"

            # --- get latest ---
            response = await client.get(
                "/api/v1/parameters/latest",
                params={"device_type": "soldering-oven"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["parameter_set"]["device_type"] == "soldering-oven"
            assert data["parameter_set"]["status"] == "active"
            assert len(data["items"]) == 2
            assert isinstance(data["checksum"], str)
            assert len(data["checksum"]) == 32

            # -- no active set for another device type ---
            response = await client.get(
                "/api/v1/parameters/latest",
                params={"device_type": "unknown-device"},
            )
            assert response.status_code == 404

            # --- record confirmation ---
            response = await client.post(
                "/api/v1/parameters/confirmations",
                json={
                    "device_id": "oven-1",
                    "device_type": "soldering-oven",
                    "parameter_set_id": set_id2,
                    "parameter_version": 2,
                    "status": "applied",
                    "message": "applied successfully",
                },
            )
            assert response.status_code == 204

            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT status FROM parameter_confirmations WHERE device_id = $1",
                    "oven-1",
                )
            assert len(rows) == 1
            assert rows[0]["status"] == "applied"
