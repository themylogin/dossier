import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
import json
from typing import TypedDict

from jsonrpcserver import Result, Success, async_dispatch
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed


class DownloadStateJson(TypedDict):
    messages_count: int
    oldest_message_date: str | None
    newest_message_date: str | None
    files_count: int
    files_pending: int
    downloaded: bool
    complete: bool


class ChatStateJson(TypedDict):
    id: int
    state: DownloadStateJson


def download_state(
    messages_count: int,
    oldest_message_date: str | None,
    newest_message_date: str | None,
    files_count: int,
    files_pending: int,
    downloaded: bool,
    complete: bool,
) -> DownloadStateJson:
    return {
        "messages_count": messages_count,
        "oldest_message_date": oldest_message_date,
        "newest_message_date": newest_message_date,
        "files_count": files_count,
        "files_pending": files_pending,
        "downloaded": downloaded,
        "complete": complete,
    }


class DownloaderApi:
    def __init__(self) -> None:
        self.states: dict[int, DownloadStateJson] = {}
        self.connections: set[ServerConnection] = set()
        self.lock = asyncio.Lock()

    async def publish(self, chat_id: int, state: DownloadStateJson) -> None:
        async with self.lock:
            self.states[chat_id] = state
            notification = json.dumps(
                {"jsonrpc": "2.0", "method": "chat_download_progress", "params": {"id": chat_id, "state": state}}
            )
            for connection in list(self.connections):
                try:
                    await connection.send(notification)
                except ConnectionClosed:
                    self.connections.discard(connection)

    @asynccontextmanager
    async def serve(
        self, host: str, port: int, on_connect: Callable[[], None], on_settings_changed: Callable[[int], None]
    ) -> AsyncIterator[Server]:
        async def settings_changed(id: int) -> Result:
            on_settings_changed(id)
            return Success(None)

        async def handle(connection: ServerConnection) -> None:
            on_connect()
            async with self.lock:
                chats: list[ChatStateJson] = [{"id": chat_id, "state": state} for chat_id, state in self.states.items()]
                await connection.send(
                    json.dumps({"jsonrpc": "2.0", "method": "chat_states", "params": {"chats": chats}})
                )
                self.connections.add(connection)
            try:
                async for message in connection:
                    if isinstance(message, str):
                        await async_dispatch(message, methods={"settings_changed": settings_changed})
            except ConnectionClosed:
                pass
            finally:
                self.connections.discard(connection)

        async with serve(handle, host, port) as server:
            yield server
