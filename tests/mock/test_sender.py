import httpx
import pytest

from process_opt.mock.sender import send_pair, send_batch


def test_send_pair_returns_true_on_202() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["X-API-Key"] == "test-key"
        assert request.headers["Content-Type"] == "application/json"
        return httpx.Response(202)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = send_pair(
        "http://localhost:8001",
        "test-key",
        {"msg": "process"},
        {"msg": "inspect"},
        client=client,
    )
    assert result is True


def test_send_pair_returns_false_on_non_202() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = send_pair(
        "http://localhost:8001",
        "test-key",
        {"msg": "process"},
        {"msg": "inspect"},
        client=client,
    )
    assert result is False


def test_send_pair_returns_false_on_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = send_pair(
        "http://localhost:8001",
        "test-key",
        {"msg": "process"},
        {"msg": "inspect"},
        client=client,
    )
    assert result is False


def test_send_batch_all_success() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(202)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pairs = [({"msg": f"p{i}"}, {"msg": f"r{i}"}) for i in range(3)]
    sent, failed = send_batch("http://localhost:8001", "test-key", pairs, client=client)
    assert sent == 3
    assert failed == 0
    assert len(calls) == 6  # 2 per pair


def test_send_batch_some_fail() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(202 if call_count <= 4 else 500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pairs = [({"msg": f"p{i}"}, {"msg": f"r{i}"}) for i in range(4)]
    sent, failed = send_batch("http://localhost:8001", "test-key", pairs, client=client)
    assert sent == 2  # first 2 pairs (4 calls) were 202
    assert failed == 2


def test_send_batch_progress_callback() -> None:
    steps: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    pairs = [({"msg": "p"}, {"msg": "r"}) for _ in range(2)]
    send_batch(
        "http://localhost:8001",
        "test-key",
        pairs,
        progress_callback=lambda n: steps.append(n),
        client=client,
    )
    assert steps == [1, 2]


@pytest.mark.asyncio
async def test_send_pair_async_returns_true_on_202() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await send_pair(
        "http://localhost:8001",
        "test-key",
        {"msg": "process"},
        {"msg": "inspect"},
        async_client=client,
    )
    assert result is True
