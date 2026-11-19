import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from jsonrpcserver import async_dispatch

from dossier.backend.api import BackendApi
from dossier.backend.downloader_api import DownloaderApiClient
from dossier.backend.progress import ProgressHub
from dossier.database import create_database_engine


def create_app(database_url: str, downloader_url: str) -> FastAPI:
    hub = ProgressHub()
    downloader_api = DownloaderApiClient(downloader_url)
    api = BackendApi(create_database_engine(database_url), hub, downloader_api)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(
            downloader_api.run({"chat_states": api.chat_states, "chat_download_progress": api.chat_download_progress})
        )
        yield
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    app = FastAPI(lifespan=lifespan)

    @app.get("/api/health")
    async def health() -> JSONResponse:
        if downloader_api.connection is None:
            return JSONResponse(status_code=503, content={"status": "downloader unavailable"})
        return JSONResponse(content={"status": "ok"})

    @app.websocket("/api/ws_jsonrpc")
    async def ws_jsonrpc(websocket: WebSocket) -> None:
        await websocket.accept()
        hub.sockets.add(websocket)
        try:
            with suppress(WebSocketDisconnect):
                while True:
                    reply = await async_dispatch(
                        await websocket.receive_text(),
                        methods={"list_chats": api.list_chats, "update_chat": api.update_chat},
                    )
                    if reply:
                        await websocket.send_text(reply)
        finally:
            hub.sockets.discard(websocket)

    return app


app = create_app("sqlite:////data/messages.db", os.environ.get("DOWNLOADER_URL", "ws://downloader:8090"))
