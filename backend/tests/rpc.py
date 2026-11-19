import time


def request(websocket, method, params=None, request_id=1):
    message = {"jsonrpc": "2.0", "method": method, "id": request_id}
    if params is not None:
        message["params"] = params
    websocket.send_json(message)
    earlier = []
    reply = websocket.receive_json()
    while reply.get("id") != request_id:
        earlier.append(reply)
        reply = websocket.receive_json()
    return reply, earlier


def list_chats(websocket):
    reply, _ = request(websocket, "list_chats")
    return reply["result"]["chats"]


def progress(websocket, chat_id, count):
    states = []
    while len(states) < count:
        message = websocket.receive_json()
        if message.get("method") == "chat_download_progress" and message["params"]["id"] == chat_id:
            states.append(message["params"]["state"])
    return states


def wait_until_all_complete(websocket):
    deadline = time.monotonic() + 5
    chats = list_chats(websocket)
    while not all(chat["state"]["complete"] for chat in chats) and time.monotonic() < deadline:
        time.sleep(0.05)
        chats = list_chats(websocket)
    return chats
