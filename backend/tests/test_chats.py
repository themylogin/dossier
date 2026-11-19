from tests.rpc import list_chats, request


def test_response_carries_the_request_id(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "list_chats", request_id=7)

    assert reply["jsonrpc"] == "2.0"
    assert reply["id"] == 7
    assert "result" in reply


def test_unknown_method_gets_an_error_and_the_connection_stays_open(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "rename_chat", request_id=8)
        chats = list_chats(websocket)

    assert reply["id"] == 8
    assert reply["error"]["code"] == -32601
    assert reply["error"]["message"] == "Method not found"
    assert chats


def test_list_chats_returns_each_chat_once(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "list_chats")

    chats = reply["result"]["chats"]
    assert list(reply["result"]) == ["chats"]
    assert chats
    assert len({chat["id"] for chat in chats}) == len(chats)


def test_each_chat_has_id_name_settings_and_state(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chats = list_chats(websocket)

    for chat in chats:
        assert set(chat) == {"id", "name", "settings", "state"}
        assert isinstance(chat["id"], int)
        assert isinstance(chat["name"], str)
        assert list(chat["settings"]) == ["media"]
        assert isinstance(chat["settings"]["media"], bool)
        assert set(chat["state"]) == {"messages_count", "oldest_message_date", "newest_message_date", "complete"}


def test_backend_starts_with_private_chats_and_groups_without_media(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chats = list_chats(websocket)

    assert any(chat["id"] > 0 for chat in chats)
    assert any(chat["id"] < 0 for chat in chats)
    assert all(chat["settings"] == {"media": False} for chat in chats)


def test_turning_media_on_stores_the_setting(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chat_id = list_chats(websocket)[0]["id"]
        reply, _ = request(websocket, "update_chat", {"id": chat_id, "settings": {"media": True}}, request_id=2)
        chats = list_chats(websocket)

    assert reply["result"]["id"] == chat_id
    assert reply["result"]["settings"] == {"media": True}
    assert next(chat for chat in chats if chat["id"] == chat_id)["settings"] == {"media": True}


def test_turning_media_off_stores_the_setting(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chat_id = list_chats(websocket)[0]["id"]
        request(websocket, "update_chat", {"id": chat_id, "settings": {"media": True}}, request_id=2)
        reply, _ = request(websocket, "update_chat", {"id": chat_id, "settings": {"media": False}}, request_id=3)

    assert reply["result"]["settings"] == {"media": False}


def test_unknown_chat_gets_an_error(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "update_chat", {"id": 999, "settings": {"media": True}}, request_id=2)

    assert reply["error"]["code"] == -32602
    assert reply["error"]["message"] == "Chat 999 not found"


def test_media_that_is_not_a_boolean_gets_invalid_params(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chat_id = list_chats(websocket)[0]["id"]
        reply, _ = request(websocket, "update_chat", {"id": chat_id, "settings": {"media": "yes"}}, request_id=2)
        chats = list_chats(websocket)

    assert reply["error"]["code"] == -32602
    assert reply["error"]["message"] == "Invalid params"
    assert next(chat for chat in chats if chat["id"] == chat_id)["settings"] == {"media": False}


def test_saved_settings_return_the_zero_state(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chat_id = list_chats(websocket)[0]["id"]
        reply, _ = request(websocket, "update_chat", {"id": chat_id, "settings": {"media": True}}, request_id=2)

    assert reply["result"]["state"] == {
        "messages_count": 0,
        "oldest_message_date": None,
        "newest_message_date": None,
        "complete": False,
    }
