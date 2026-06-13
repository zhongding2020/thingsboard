from collections.abc import Awaitable, Callable

import nats
from nats.errors import TimeoutError
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig
from nats.js.errors import FetchTimeoutError, NotFoundError

from process_opt.common.settings import Settings
from process_opt.consumer.handler import MessageHandler, RawMessage


async def consume_pending_messages(
    settings: Settings,
    handler: MessageHandler,
    *,
    batch_size: int = 10,
    durable_prefix: str = "process-opt",
) -> int:
    nc = await nats.connect(settings.nats_url)
    try:
        js = nc.jetstream()
        handled = 0
        handled += await _consume_subject(
            js,
            settings.nats_stream,
            settings.process_subject,
            f"{durable_prefix}-process",
            handler.handle_process,
            batch_size,
        )
        handled += await _consume_subject(
            js,
            settings.nats_stream,
            settings.inspection_subject,
            f"{durable_prefix}-inspection",
            handler.handle_inspection,
            batch_size,
        )
        return handled
    finally:
        await nc.close()


async def _consume_subject(
    js: JetStreamContext,
    stream: str,
    subject: str,
    durable: str,
    handle: Callable[[RawMessage], Awaitable[None]],
    batch_size: int,
) -> int:
    try:
        subscription = await js.pull_subscribe(
            subject,
            durable=durable,
            stream=stream,
            config=ConsumerConfig(filter_subject=subject),
        )
    except NotFoundError:
        return 0

    try:
        messages = await subscription.fetch(batch=batch_size, timeout=1)
    except (TimeoutError, FetchTimeoutError):
        return 0

    for message in messages:
        await handle(message)
    return len(messages)


__all__ = ["MessageHandler", "consume_pending_messages"]
