from typing import Any

from starlette.testclient import WebSocketTestSession


def request(
    websocket: WebSocketTestSession, method: str, params: dict[str, object] | None = None, request_id: int = 1
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    message = {"jsonrpc": "2.0", "method": method, "id": request_id}
    if params is not None:
        message["params"] = params
    websocket.send_json(message)
    earlier: list[dict[str, Any]] = []
    reply = websocket.receive_json()
    while reply.get("id") != request_id:
        earlier.append(reply)
        reply = websocket.receive_json()
    return reply, earlier


def list_chats(websocket: WebSocketTestSession) -> list[dict[str, Any]]:
    reply, _ = request(websocket, "list_chats")
    chats: list[dict[str, Any]] = reply["result"]["chats"]
    return chats


def progress(websocket: WebSocketTestSession, chat_id: int, count: int) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    while len(states) < count:
        message = websocket.receive_json()
        if message.get("method") == "chat_download_progress" and message["params"]["id"] == chat_id:
            states.append(message["params"]["state"])
    return states
