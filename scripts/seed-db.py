"""Direct database seeding script.

Bypasses the gateway/NATS/consumer pipeline and inserts mock data directly
into PostgreSQL. Intended to be run after backend startup to populate the
database with baseline data.

Usage:
    python scripts/seed-db.py --dsn "postgresql://postgres:postgres@localhost:5432/process_opt"
"""

from __future__ import annotations

import argparse
import asyncio
import random
from datetime import UTC, datetime, timedelta

import asyncpg

from process_opt.mock.generator import generate_pair
from process_opt.mock.templates import DEVICE_TEMPLATES

BATCH_SIZE = 1000


async def ensure_lines(pool: asyncpg.Pool) -> dict[str, str]:
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
            try:
                row = await conn.fetchrow(
                    "INSERT INTO production_lines (name, responsible, location) VALUES ($1, $2, $3) "
                    "ON CONFLICT (name) DO UPDATE SET name=production_lines.name RETURNING id",
                    name, responsible, location,
                )
                if row:
                    line_map[name] = row["id"]
            except Exception:
                row = await conn.fetchrow(
                    "SELECT id FROM production_lines WHERE name = $1", name,
                )
                if row:
                    line_map[name] = row["id"]
    return line_map


async def ensure_devices(
    pool: asyncpg.Pool,
    line_map: dict[str, str],
    device_count: int,
) -> list[str]:
    # Map device types to lines
    type_to_line = {
        "reflow-oven": "SMT-A-01",
        "injection-molder": "注塑-A线",
        "pick-and-place": "SMT-A-02",
        "wave-solder": "SMT-B-01",
        "cnc-drill": "CNC-A线",
        "3d-printer": "3D打印-A线",
        "testing-station": "电测-A线",
        "laser-cutter": "激光切割线",
        "coating-machine": "涂覆-A线",
        "xray-inspection": "X光检测线",
        "oven-curing": "固化-A线",
        "wire-bonder": "键合-A线",
        "ultrasonic-cleaner": "涂覆-B线",
    }

    device_ids: list[str] = []
    async with pool.acquire() as conn:
        for device_type, line_name in type_to_line.items():
            for i in range(1, device_count + 1):
                dev_id = f"{device_type}-{i:03d}"
                line_id = line_map.get(line_name)
                await conn.execute(
                    "INSERT INTO device_registry (id, line_id, name, type, icon, description) "
                    "VALUES ($1, $2, $3, $4, 'Monitor', $5) "
                    "ON CONFLICT (id) DO UPDATE SET line_id = EXCLUDED.line_id",
                    dev_id, line_id, dev_id, device_type, f"{line_name}设备",
                )
                device_ids.append(dev_id)

    return device_ids


async def seed_data(
    pool: asyncpg.Pool,
    device_ids: list[str],
    count: int,
) -> int:
    total = 0
    base_time = datetime.now(UTC) - timedelta(days=30)

    for batch_start in range(0, count, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, count)
        batch_size = batch_end - batch_start

        process_rows: list[tuple] = []
        inspect_rows: list[tuple] = []

        for i in range(batch_size):
            device_id = random.choice(device_ids)
            barcode = f"DB-{datetime.now(UTC).strftime('%y%m%d')}-{total + i + 1:06d}"
            ts = base_time + timedelta(minutes=total + i)

            proc_payload, insp_payload = generate_pair(
                device_id.rsplit("-", 1)[0],
                barcode,
                int(device_id.rsplit("-", 1)[-1]),
            )
            import json
            process_rows.append((
                barcode,
                device_id,
                ts,
                json.dumps(proc_payload["params"]),
            ))
            inspect_rows.append((
                barcode,
                "station-" + device_id.rsplit("-", 1)[0],
                ts,
                json.dumps(insp_payload["results"]),
            ))

        async with pool.acquire() as conn:
            await conn.executemany(
                "INSERT INTO process_summary (barcode, device_id, processed_at, params) "
                "VALUES ($1, $2, $3, $4::jsonb) ON CONFLICT (barcode) DO NOTHING",
                process_rows,
            )
            await conn.executemany(
                "INSERT INTO inspection_results (barcode, station_id, inspected_at, results) "
                "VALUES ($1, $2, $3, $4::jsonb) ON CONFLICT (barcode) DO NOTHING",
                inspect_rows,
            )

        total += batch_size
        print(f"  {total}/{count} records inserted")

    return total


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed database directly")
    parser.add_argument("--dsn", default="postgresql://postgres:postgres@localhost:5432/process_opt")
    parser.add_argument("--device-count", type=int, default=30, help="Devices per type")
    parser.add_argument("--records", type=int, default=5000, help="Total records per device type (default 5000)")
    args = parser.parse_args()

    pool = await asyncpg.create_pool(args.dsn)
    try:
        print("Creating lines...")
        line_map = await ensure_lines(pool)
        print(f"  {len(line_map)} lines ready")

        print("Registering devices...")
        device_ids = await ensure_devices(pool, line_map, args.device_count)
        print(f"  {len(device_ids)} devices registered")

        print(f"Seeding {args.records} records per type...")
        total = await seed_data(pool, device_ids, args.records)
        print(f"Done! {total} total records inserted")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
