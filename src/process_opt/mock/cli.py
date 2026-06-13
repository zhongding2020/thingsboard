import asyncio
import time
from uuid import uuid4

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
