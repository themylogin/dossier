import asyncio
from collections.abc import Coroutine
import json
from pathlib import Path
import queue
import sqlite3
import threading
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve

from dossier.downloader.api import ChatStateJson, DownloadStateJson


class FakeDownloaderServer:
    def __init__(self, chats: list[ChatStateJson], database_path: Path, port: int = 0) -> None:
        self.chats = chats
        self.database_path = database_path
        self.received: queue.Queue[tuple[dict[str, Any], int]] = queue.Queue()
        self.connections: set[ServerConnection] = set()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.server = self.call(self.start(port))
        self.port: int = self.server.sockets[0].getsockname()[1]

    def call[T](self, coroutine: Coroutine[Any, Any, T]) -> T:
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout=10)

    async def start(self, port: int) -> Server:
        return await serve(self.handle, "127.0.0.1", port)

    async def handle(self, connection: ServerConnection) -> None:
        await connection.send(json.dumps({"jsonrpc": "2.0", "method": "chat_states", "params": {"chats": self.chats}}))
        self.connections.add(connection)
        try:
            async for message in connection:
                notice = json.loads(message)
                with sqlite3.connect(self.database_path) as database:
                    media = database.execute(
                        "SELECT download_media FROM chats WHERE chat_id = ?", (notice["params"]["id"],)
                    ).fetchone()[0]
                self.received.put((notice, media))
        finally:
            self.connections.discard(connection)

    def push(self, chat_id: int, state: DownloadStateJson) -> None:
        message = json.dumps(
            {"jsonrpc": "2.0", "method": "chat_download_progress", "params": {"id": chat_id, "state": state}}
        )

        async def broadcast() -> None:
            for connection in list(self.connections):
                await connection.send(message)

        self.call(broadcast())

    def stop(self) -> None:
        if not self.thread.is_alive():
            return

        async def close() -> None:
            self.server.close()
            await self.server.wait_closed()

        self.call(close())
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=10)
