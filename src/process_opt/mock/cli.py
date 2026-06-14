import asyncio
import random
import time
from datetime import UTC, datetime, timedelta
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


async def _ensure_lines(pool: asyncpg.Pool) -> dict[str, str]:
    lines = [
        ("SMT-A-01", "张工", "A栋2层-A区"),
        ("SMT-A-02", "张工", "A栋2层-B区"),
        ("SMT-B-01", "刘工", "A栋3层-A区"),
        ("SMT-B-02", "刘工", "A栋3层-B区"),
        ("注塑-A线", "李工", "B栋1层-东"),
        ("注塑-B线", "王工", "B栋1层-西"),
        ("注塑-C线", "陈工", "B栋2层-东"),
        ("CNC-A线", "赵工", "C栋1层-东"),
        ("CNC-B线", "赵工", "C栋1层-西"),
        ("CNC-C线", "钱工", "C栋1层-中"),
        ("3D打印-A线", "孙工", "C栋2层"),
        ("3D打印-B线", "孙工", "C栋2层"),
        ("激光切割线", "周工", "C栋3层"),
        ("涂覆-A线", "吴工", "D栋1层"),
        ("涂覆-B线", "郑工", "D栋1层"),
        ("X光检测线", "冯工", "D栋2层"),
        ("电测-A线", "褚工", "D栋3层"),
        ("电测-B线", "褚工", "D栋3层"),
        ("固化-A线", "卫工", "E栋1层"),
        ("键合-A线", "蒋工", "E栋2层"),
    ]
    line_map: dict[str, str] = {}
    async with pool.acquire() as conn:
        for name, responsible, location in lines:
            row = await conn.fetchrow(
                "INSERT INTO production_lines (name, responsible, location) VALUES ($1,$2,$3) "
                "ON CONFLICT (name) DO NOTHING RETURNING id",
                name, responsible, location,
            )
            if row:
                line_map[name] = row["id"]
            else:
                r2 = await conn.fetchrow("SELECT id FROM production_lines WHERE name=$1", name)
                if r2:
                    line_map[name] = r2["id"]
    return line_map


async def _register_devices(pool: asyncpg.Pool, line_map: dict[str, str], device_count: int) -> list[str]:
    type_to_line = {
        "reflow-oven": "SMT-A-01", "injection-molder": "注塑-A线",
        "pick-and-place": "SMT-A-02", "wave-solder": "SMT-B-01",
        "cnc-drill": "CNC-A线", "3d-printer": "3D打印-A线",
        "testing-station": "电测-A线", "laser-cutter": "激光切割线",
        "coating-machine": "涂覆-A线", "xray-inspection": "X光检测线",
        "oven-curing": "固化-A线", "wire-bonder": "键合-A线",
        "ultrasonic-cleaner": "涂覆-B线",
    }
    device_ids: list[str] = []
    async with pool.acquire() as conn:
        for dtype, line_name in type_to_line.items():
            line_id = line_map.get(line_name)
            for i in range(1, device_count + 1):
                dev_id = f"{dtype}-{i:03d}"
                await conn.execute(
                    "INSERT INTO device_registry (id, line_id, name, type, icon, description) "
                    "VALUES ($1,$2,$3,$4,'Monitor',$5) ON CONFLICT (id) DO UPDATE SET line_id=EXCLUDED.line_id",
                    dev_id, line_id, dev_id, dtype, f"{line_name}设备",
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
