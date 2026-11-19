import asyncio
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
import json
import logging

from jsonrpcserver import Result, async_dispatch
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger(__name__)


class DownloaderApiClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self.connection: ClientConnection | None = None

    async def run(
        self, methods: Mapping[str, Callable[..., Awaitable[Result]]], on_disconnect: Callable[[], Awaitable[None]]
    ) -> None:
        while True:
            try:
                async with connect(self.url) as connection:
                    self.connection = connection
                    logger.info(f"Connected to the downloader at {self.url}")
                    async for message in connection:
                        if isinstance(message, str):
                            await async_dispatch(message, methods=methods)
            except (OSError, WebSocketException) as error:
                logger.warning(f"No connection to the downloader at {self.url}: {error}")
            if self.connection is not None:
                self.connection = None
                await on_disconnect()
            await asyncio.sleep(1)

    async def settings_changed(self, chat_id: int) -> None:
        if self.connection is None:
            return
        with suppress(ConnectionClosed):
            await self.connection.send(
                json.dumps({"jsonrpc": "2.0", "method": "settings_changed", "params": {"id": chat_id}})
            )
