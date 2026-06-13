from collections.abc import Callable, Coroutine
from typing import Any, overload

import httpx


@overload
def send_pair(
    gateway_url: str,
    api_key: str,
    process_payload: dict[str, Any],
    inspection_payload: dict[str, Any],
    *,
    client: httpx.Client | None = ...,
    async_client: None = ...,
) -> bool: ...


@overload
def send_pair(
    gateway_url: str,
    api_key: str,
    process_payload: dict[str, Any],
    inspection_payload: dict[str, Any],
    *,
    client: None = ...,
    async_client: httpx.AsyncClient | None = ...,
) -> Coroutine[Any, Any, bool]: ...


def send_pair(
    gateway_url: str,
    api_key: str,
    process_payload: dict[str, Any],
    inspection_payload: dict[str, Any],
    *,
    client: httpx.Client | None = None,
    async_client: httpx.AsyncClient | None = None,
) -> bool | Coroutine[Any, Any, bool]:
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }
    process_url = f"{gateway_url}/api/v1/data/process"
    inspection_url = f"{gateway_url}/api/v1/data/inspection"

    if async_client is not None:
        return _send_async(async_client, process_url, inspection_url, headers, process_payload, inspection_payload)

    close = client is None
    client = client or httpx.Client()
    try:
        return _send_sync(client, process_url, inspection_url, headers, process_payload, inspection_payload)
    finally:
        if close:
            client.close()


def _send_sync(
    client: httpx.Client,
    process_url: str,
    inspection_url: str,
    headers: dict[str, str],
    process_payload: dict[str, Any],
    inspection_payload: dict[str, Any],
) -> bool:
    try:
        r1 = client.post(process_url, json=process_payload, headers=headers)
        r2 = client.post(inspection_url, json=inspection_payload, headers=headers)
        return r1.status_code == 202 and r2.status_code == 202
    except httpx.HTTPError:
        return False


async def _send_async(
    client: httpx.AsyncClient,
    process_url: str,
    inspection_url: str,
    headers: dict[str, str],
    process_payload: dict[str, Any],
    inspection_payload: dict[str, Any],
) -> bool:
    try:
        r1 = await client.post(process_url, json=process_payload, headers=headers)
        r2 = await client.post(inspection_url, json=inspection_payload, headers=headers)
        return r1.status_code == 202 and r2.status_code == 202
    except httpx.HTTPError:
        return False


def send_batch(
    gateway_url: str,
    api_key: str,
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    progress_callback: Callable[[int], None] | None = None,
    client: httpx.Client | None = None,
) -> tuple[int, int]:
    close = client is None
    client = client or httpx.Client()
    sent = 0
    failed = 0
    try:
        for process_payload, inspection_payload in pairs:
            if send_pair(gateway_url, api_key, process_payload, inspection_payload, client=client):
                sent += 1
            else:
                failed += 1
            if progress_callback:
                progress_callback(sent + failed)
    finally:
        if close:
            client.close()
    return sent, failed
