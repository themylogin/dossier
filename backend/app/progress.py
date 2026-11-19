import json

from fastapi import WebSocket, WebSocketDisconnect

from app.chats import DownloadState


class ProgressHub:
    def __init__(self) -> None:
        self.sockets: set[WebSocket] = set()

    async def publish(self, chat_id: int, state: DownloadState) -> None:
        notification = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "chat_download_progress",
                "params": {"id": chat_id, "state": state.model_dump(mode="json")},
            }
        )
        for websocket in list(self.sockets):
            try:
                await websocket.send_text(notification)
            except (WebSocketDisconnect, RuntimeError):
                self.sockets.discard(websocket)
