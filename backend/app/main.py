from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from jsonrpcserver import Error, InvalidParams, Result, Success, async_dispatch
from pydantic import ValidationError

from app.chats import UpdateChatParams, fake_chats
from app.progress import ProgressHub
from app.stub_downloader import StubDownloader


def create_app(step_seconds: float) -> FastAPI:
    chats = fake_chats()
    hub = ProgressHub()
    downloader = StubDownloader(chats, hub, step_seconds)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        for chat_id in chats:
            downloader.start(chat_id)
        yield
        await downloader.close()

    async def list_chats() -> Result:
        return Success({"chats": [chat.model_dump(mode="json") for chat in chats.values()]})

    async def update_chat(id: object, settings: object) -> Result:
        try:
            params = UpdateChatParams.model_validate({"id": id, "settings": settings})
        except ValidationError:
            return InvalidParams()
        chat = chats.get(params.id)
        if chat is None:
            return Error(-32602, f"Chat {params.id} not found")
        chat.settings = params.settings
        downloader.start(chat.id)
        return Success(chat.model_dump(mode="json"))

    methods = {"list_chats": list_chats, "update_chat": update_chat}
    app = FastAPI(lifespan=lifespan)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/api/ws_jsonrpc")
    async def ws_jsonrpc(websocket: WebSocket) -> None:
        await websocket.accept()
        hub.sockets.add(websocket)
        try:
            with suppress(WebSocketDisconnect):
                while True:
                    reply = await async_dispatch(await websocket.receive_text(), methods=methods)
                    if reply:
                        await websocket.send_text(reply)
        finally:
            hub.sockets.discard(websocket)

    return app


app = create_app(0.5)
