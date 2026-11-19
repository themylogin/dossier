from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
from sqlalchemy import Engine, event
from sqlalchemy.pool import ConnectionPoolEntry

from dossier.backend.main import create_app
from tests.backend.conftest import store_messages
from tests.backend.rpc import list_chats, request


def test_response_carries_the_request_id(client: TestClient) -> None:
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "list_chats", request_id=7)

    assert reply["jsonrpc"] == "2.0"
    assert reply["id"] == 7
    assert "result" in reply


def test_unknown_method_gets_an_error_and_the_connection_stays_open(client: TestClient) -> None:
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "rename_chat", request_id=8)
        chats = list_chats(websocket)

    assert reply["id"] == 8
    assert reply["error"]["code"] == -32601
    assert reply["error"]["message"] == "Method not found"
    assert chats


def test_list_chats_returns_every_chat_in_the_database(client: TestClient) -> None:
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "list_chats")

    assert list(reply["result"]) == ["chats"]
    assert sorted((chat["id"], chat["name"]) for chat in reply["result"]["chats"]) == [
        (-2001, "Family"),
        (1001, "Alice Smith"),
    ]


def test_each_chat_has_id_name_settings_and_state(client: TestClient) -> None:
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chats = list_chats(websocket)

    for chat in chats:
        assert set(chat) == {"id", "name", "settings", "state"}
        assert isinstance(chat["id"], int)
        assert isinstance(chat["name"], str)
        assert chat["settings"] == {"media": False}
        assert set(chat["state"]) == {"messages_count", "oldest_message_date", "newest_message_date", "complete"}


def test_chat_without_a_reported_state_has_the_state_of_its_stored_messages(
    client: TestClient, database_path: Path
) -> None:
    store_messages(database_path, 1001, 3)

    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chats = list_chats(websocket)

    assert next(chat for chat in chats if chat["id"] == 1001)["state"] == {
        "messages_count": 3,
        "oldest_message_date": "2024-01-01T10:00:00Z",
        "newest_message_date": "2024-01-03T10:00:00Z",
        "complete": None,
    }


def test_chat_without_messages_has_the_zero_state(client: TestClient) -> None:
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chats = list_chats(websocket)

    assert all(
        chat["state"]
        == {"messages_count": 0, "oldest_message_date": None, "newest_message_date": None, "complete": None}
        for chat in chats
    )


def test_turning_media_on_stores_the_setting(client: TestClient) -> None:
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "update_chat", {"id": 1001, "settings": {"media": True}}, request_id=2)
        chats = list_chats(websocket)

    assert reply["result"] == {
        "id": 1001,
        "name": "Alice Smith",
        "settings": {"media": True},
        "state": {"messages_count": 0, "oldest_message_date": None, "newest_message_date": None, "complete": None},
    }
    assert next(chat for chat in chats if chat["id"] == 1001)["settings"] == {"media": True}


def test_turning_media_off_stores_the_setting(client: TestClient) -> None:
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        request(websocket, "update_chat", {"id": 1001, "settings": {"media": True}}, request_id=2)
        reply, _ = request(websocket, "update_chat", {"id": 1001, "settings": {"media": False}}, request_id=3)

    assert reply["result"]["settings"] == {"media": False}


def test_unknown_chat_gets_an_error(client: TestClient) -> None:
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "update_chat", {"id": 999, "settings": {"media": True}}, request_id=2)

    assert reply["error"]["code"] == -32602
    assert reply["error"]["message"] == "Chat 999 not found"


def test_media_that_is_not_a_boolean_gets_invalid_params(client: TestClient) -> None:
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "update_chat", {"id": 1001, "settings": {"media": "yes"}}, request_id=2)
        chats = list_chats(websocket)

    assert reply["error"]["code"] == -32602
    assert reply["error"]["message"] == "Invalid params"
    assert next(chat for chat in chats if chat["id"] == 1001)["settings"] == {"media": False}


def test_settings_survive_a_restart(database_path: Path) -> None:
    url = f"sqlite:///{database_path}"
    with TestClient(create_app(url, "ws://127.0.0.1:9")) as first_run:
        with first_run.websocket_connect("/api/ws_jsonrpc") as websocket:
            request(websocket, "update_chat", {"id": 1001, "settings": {"media": True}}, request_id=2)

    with TestClient(create_app(url, "ws://127.0.0.1:9")) as second_run:
        with second_run.websocket_connect("/api/ws_jsonrpc") as websocket:
            chats = list_chats(websocket)

    assert next(chat for chat in chats if chat["id"] == 1001)["settings"] == {"media": True}


def test_update_chat_result_has_the_state_of_the_stored_messages(client: TestClient, database_path: Path) -> None:
    store_messages(database_path, 1001, 3)

    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        reply, _ = request(websocket, "update_chat", {"id": 1001, "settings": {"media": True}}, request_id=2)

    assert reply["result"]["state"]["messages_count"] == 3


def test_update_chat_starts_with_begin_immediate(client: TestClient) -> None:
    statements: list[str] = []

    def trace(dbapi_connection: sqlite3.Connection, record: ConnectionPoolEntry) -> None:
        dbapi_connection.set_trace_callback(statements.append)

    event.listen(Engine, "connect", trace)
    try:
        with client.websocket_connect("/api/ws_jsonrpc") as websocket:
            request(websocket, "update_chat", {"id": 1001, "settings": {"media": True}}, request_id=2)
    finally:
        event.remove(Engine, "connect", trace)

    update_index = next(index for index, statement in enumerate(statements) if statement.startswith("UPDATE chats"))
    assert statements[update_index - 1] == "BEGIN IMMEDIATE"
