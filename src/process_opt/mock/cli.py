import time
from uuid import uuid4

import click

from process_opt.mock.generator import generate_pair
from process_opt.mock.sender import send_pair


@click.group()
def main() -> None:
    """Process optimization mock data generator."""


@main.command()
@click.option("--count", default=100, show_default=True, help="Number of messages to generate")
@click.option("--device-type", default="reflow-oven", show_default=True, help="Device type")
@click.option("--gateway-url", default="http://localhost:8001", show_default=True, help="Gateway URL")
@click.option("--api-key", default="dev-api-key", show_default=True, help="API key")
def seed(count: int, device_type: str, gateway_url: str, api_key: str) -> None:
    """Generate and send a batch of mock data."""
    sent = 0
    failed = 0
    for i in range(count):
        barcode = f"MOCK-{uuid4().hex[:8].upper()}"
        process_payload, inspection_payload = generate_pair(device_type, barcode)
        ok = send_pair(gateway_url, api_key, process_payload, inspection_payload)
        if ok:
            sent += 1
        else:
            failed += 1
        click.echo(f"[{i + 1}/{count}] {'OK' if ok else 'FAIL'} {barcode}")
    click.echo(f"\nDone: {sent} sent, {failed} failed")


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
