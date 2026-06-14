import asyncio
import random
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import asyncpg
import click

from process_opt.mock.generator import generate_pair
from process_opt.mock.sender import send_batch, send_pair


@click.group()
def main() -> None:
    """Process optimization mock data generator."""


@main.command()
@click.option("--count", default=100, show_default=True, help="Number of messages to generate")
@click.option("--device-type", default="reflow-oven", show_default=True, help="Device type")
@click.option("--gateway-url", default="http://localhost:8001", show_default=True, help="Gateway URL")
@click.option("--api-key", default="dev-api-key", show_default=True, help="API key")
@click.option("--db-dsn", default=None, help="PostgreSQL DSN for device registration")
@click.option("--device-count", default=10, help="Number of devices to register per type")
def seed(count: int, device_type: str, gateway_url: str, api_key: str, db_dsn: str | None, device_count: int) -> None:
    """Generate and send a batch of mock data."""
    if db_dsn:
        asyncio.run(_pre_register_devices(db_dsn, device_type, device_count))

    pairs = [
        generate_pair(device_type, f"MOCK-{uuid4().hex[:8].upper()}", (i % device_count) + 1)
        for i in range(count)
    ]
    sent, failed = send_batch(gateway_url, api_key, pairs)
    click.echo(f"\nDone: {sent} sent, {failed} failed")


async def _pre_register_devices(dsn: str, device_type: str, count: int) -> None:
    """Pre-register device_count devices of the given type in device_registry."""
    from process_opt.common.db import create_pool
    from process_opt.common.repositories import LineDeviceRepository
    pool = await create_pool(dsn)
    try:
        repo = LineDeviceRepository(pool)
        for i in range(1, count + 1):
            device_id = f"{device_type}-{i:03d}"
            await repo.ensure_device_exists(device_id, device_type)
    finally:
        await pool.close()


@main.command()
@click.option("--interval", default=5, show_default=True, help="Seconds between messages")
@click.option("--device-type", default="reflow-oven", show_default=True, help="Device type")
@click.option("--gateway-url", default="http://localhost:8001", show_default=True, help="Gateway URL")
@click.option("--api-key", default="dev-api-key", show_default=True, help="API key")
def stream(interval: int, device_type: str, gateway_url: str, api_key: str) -> None:
    """Continuously generate and send mock data at intervals."""
    click.echo(f"Streaming {device_type} data every {interval}s to {gateway_url}")
    counter = 0
    while True:
        barcode = f"MOCK-{uuid4().hex[:8].upper()}"
        process_payload, inspection_payload = generate_pair(device_type, barcode)
        ok = send_pair(gateway_url, api_key, process_payload, inspection_payload)
        counter += 1
        click.echo(f"[{counter}] {'OK' if ok else 'FAIL'} {barcode}")
        time.sleep(interval)


@main.command()
@click.option("--dsn", default="postgresql://postgres:postgres@localhost:5432/process_opt", help="PostgreSQL DSN")
@click.option("--device-count", default=30, show_default=True, help="Devices per type")
@click.option("--records", default=5000, show_default=True, help="Total records to generate")
@click.option("--clear", is_flag=True, help="Clear existing data before seeding")
def seed_db(dsn: str, device_count: int, records: int, clear: bool) -> None:
    """Seed database directly (bypass gateway/NATS)."""
    import asyncio

    async def _run() -> None:
        pool = await asyncpg.create_pool(dsn)
        try:
            if clear:
                async with pool.acquire() as conn:
                    await conn.execute("DELETE FROM inspection_results")
                    await conn.execute("DELETE FROM process_summary")
                    await conn.execute("DELETE FROM device_registry WHERE id LIKE '%-%'")
                    await conn.execute("DELETE FROM production_lines WHERE name != '默认产线'")
                click.echo("Old data cleared")

            click.echo("Creating lines...")
            line_map = await _ensure_lines(pool)
            click.echo(f"  {len(line_map)} lines ready")

            click.echo("Registering devices...")
            device_ids = await _register_devices(pool, line_map, device_count)
            click.echo(f"  {len(device_ids)} devices registered")

            click.echo(f"Seeding {records} records...")
            total = await _insert_records(pool, device_ids, records)
            click.echo(f"Done! {total} total records inserted")
        finally:
            await pool.close()

    asyncio.run(_run())


LINE_DEFS: list[dict[str, Any]] = [
    {"name": "PCBA-A线", "responsible": "张工", "location": "A栋1层",
     "devices": {"reflow-oven": 2, "pick-and-place": 2, "wave-solder": 1, "xray-inspection": 1, "testing-station": 1, "oven-curing": 1}},
    {"name": "PCBA-B线", "responsible": "李工", "location": "A栋2层",
     "devices": {"reflow-oven": 2, "pick-and-place": 2, "wave-solder": 1, "xray-inspection": 1, "testing-station": 1}},
    {"name": "SMT-A线", "responsible": "王工", "location": "A栋3层",
     "devices": {"pick-and-place": 3, "reflow-oven": 2, "xray-inspection": 1}},
    {"name": "DIP-A线", "responsible": "赵工", "location": "B栋1层",
     "devices": {"wave-solder": 2, "ultrasonic-cleaner": 1, "coating-machine": 1}},
    {"name": "组装-A线", "responsible": "钱工", "location": "B栋2层",
     "devices": {"wire-bonder": 2, "coating-machine": 1, "ultrasonic-cleaner": 1, "laser-cutter": 1}},
    {"name": "机加-A线", "responsible": "孙工", "location": "C栋1层",
     "devices": {"cnc-drill": 3, "laser-cutter": 1, "3d-printer": 2}},
    {"name": "注塑-A线", "responsible": "周工", "location": "C栋2层",
     "devices": {"injection-molder": 3}},
    {"name": "检测-A线", "responsible": "吴工", "location": "D栋1层",
     "devices": {"testing-station": 2, "xray-inspection": 1}},
    {"name": "老化-A线", "responsible": "郑工", "location": "D栋2层",
     "devices": {"oven-curing": 2}},
    {"name": "键合-A线", "responsible": "冯工", "location": "E栋1层",
     "devices": {"wire-bonder": 2}},
]


async def _ensure_lines(pool: asyncpg.Pool) -> dict[str, str]:
    line_map: dict[str, str] = {}
    async with pool.acquire() as conn:
        for ld in LINE_DEFS:
            row = await conn.fetchrow(
                "INSERT INTO production_lines (name, responsible, location) VALUES ($1,$2,$3) "
                "ON CONFLICT (name) DO NOTHING RETURNING id",
                ld["name"], ld["responsible"], ld["location"],
            )
            if row:
                line_map[ld["name"]] = row["id"]
            else:
                r2 = await conn.fetchrow("SELECT id FROM production_lines WHERE name=$1", ld["name"])
                if r2:
                    line_map[ld["name"]] = r2["id"]
    return line_map


async def _register_devices(pool: asyncpg.Pool, line_map: dict[str, str], device_count: int) -> list[str]:
    device_ids: list[str] = []
    counters: dict[str, int] = {}
    async with pool.acquire() as conn:
        for ld in LINE_DEFS:
            line_id = line_map.get(ld["name"])
            for dtype, count in ld["devices"].items():
                for _ in range(count):
                    counters[dtype] = counters.get(dtype, 0) + 1
                    dev_id = f"{dtype}-{counters[dtype]:03d}"
                    await conn.execute(
                        "INSERT INTO device_registry (id, line_id, name, type, icon, description) "
                        "VALUES ($1,$2,$3,$4,'Monitor',$5) ON CONFLICT (id) DO UPDATE SET line_id=EXCLUDED.line_id",
                        dev_id, line_id, dev_id, dtype, f"{ld['name']}设备",
                    )
                    device_ids.append(dev_id)
    return device_ids


async def _insert_records(pool: asyncpg.Pool, device_ids: list[str], count: int) -> int:
    import json
    BATCH = 1000
    total = 0
    base_time = datetime.now(UTC) - timedelta(days=30)
    while total < count:
        batch_end = min(total + BATCH, count)
        batch_size = batch_end - total
        process_rows: list[tuple] = []
        inspect_rows: list[tuple] = []
        for i in range(batch_size):
            dev_id = random.choice(device_ids)
            barcode = f"DB-{datetime.now(UTC).strftime('%y%m%d')}-{total + i + 1:06d}"
            ts = base_time + timedelta(minutes=total + i)
            proc_payload, insp_payload = generate_pair(
                dev_id.rsplit("-", 1)[0], barcode, int(dev_id.rsplit("-", 1)[-1]),
            )
            process_rows.append((
                barcode, dev_id, ts,
                json.dumps(proc_payload["params"]),
                proc_payload["product_model"],
            ))
            inspect_rows.append((
                barcode, "station-" + dev_id.rsplit("-", 1)[0], ts,
                json.dumps(insp_payload["results"]),
                insp_payload["product_model"],
            ))
        async with pool.acquire() as conn:
            await conn.executemany(
                """INSERT INTO process_summary (barcode, device_id, processed_at, params, product_model)
                   VALUES ($1,$2,$3,$4::jsonb,$5) ON CONFLICT (barcode) DO NOTHING""",
                process_rows,
            )
            await conn.executemany(
                """INSERT INTO inspection_results (barcode, station_id, inspected_at, results, product_model)
                   VALUES ($1,$2,$3,$4::jsonb,$5) ON CONFLICT (barcode) DO NOTHING""",
                inspect_rows,
            )
        total += batch_size
        click.echo(f"  {total}/{count}")
    return total
