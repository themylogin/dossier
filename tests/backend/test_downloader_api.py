from pathlib import Path

from fastapi.testclient import TestClient

from dossier.downloader.api import DownloadStateJson
from tests.backend.conftest import store_messages, wait_for_link
from tests.backend.fake_downloader import FakeDownloaderServer
from tests.backend.rpc import list_chats, progress, request


def downloader_state(messages_count: int) -> DownloadStateJson:
    return {
        "messages_count": messages_count,
        "oldest_message_date": "2024-01-01T10:00:00+00:00",
        "newest_message_date": "2024-01-02T10:00:00+00:00",
        "files_count": 0,
        "files_pending": 0,
        "downloaded": False,
        "complete": False,
    }


def test_media_turned_on_is_stored_before_the_downloader_gets_the_notice(
    linked_client: TestClient, fake_downloader: FakeDownloaderServer
) -> None:
    with linked_client.websocket_connect("/api/ws_jsonrpc") as websocket:
        request(websocket, "update_chat", {"id": 1001, "settings": {"media": True}}, request_id=2)

    notice, media_at_notice = fake_downloader.received.get(timeout=5)
    assert notice == {"jsonrpc": "2.0", "method": "settings_changed", "params": {"id": 1001}}
    assert media_at_notice == 1


def test_reported_state_wins_over_the_stored_messages(linked_client: TestClient, database_path: Path) -> None:
    store_messages(database_path, 1001, 3)

    with linked_client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chats = list_chats(websocket)

    assert next(chat for chat in chats if chat["id"] == 1001)["state"] == {
        "messages_count": 7,
        "oldest_message_date": "2024-01-01T10:00:00Z",
        "newest_message_date": "2024-01-02T10:00:00Z",
        "files_count": 0,
        "files_pending": 0,
        "downloaded": False,
        "complete": True,
    }


def test_two_clients_get_the_same_progress(linked_client: TestClient, fake_downloader: FakeDownloaderServer) -> None:
    with (
        linked_client.websocket_connect("/api/ws_jsonrpc") as first,
        linked_client.websocket_connect("/api/ws_jsonrpc") as second,
    ):
        list_chats(first)
        list_chats(second)
        fake_downloader.push(1001, downloader_state(100))
        first_states = progress(first, 1001, 1)
        second_states = progress(second, 1001, 1)

    assert first_states == second_states
    assert first_states[0]["messages_count"] == 100


def test_a_closed_client_does_not_stop_progress_for_others(
    linked_client: TestClient, fake_downloader: FakeDownloaderServer
) -> None:
    with linked_client.websocket_connect("/api/ws_jsonrpc") as staying:
        list_chats(staying)
        with linked_client.websocket_connect("/api/ws_jsonrpc") as leaving:
            list_chats(leaving)
        fake_downloader.push(1001, downloader_state(200))
        states = progress(staying, 1001, 1)

    assert states[0]["messages_count"] == 200


def test_downloader_restart_brings_a_new_snapshot_to_the_ui(
    linked_client: TestClient, fake_downloader: FakeDownloaderServer, database_path: Path
) -> None:
    with linked_client.websocket_connect("/api/ws_jsonrpc") as websocket:
        list_chats(websocket)
        fake_downloader.stop()
        assert wait_for_link(linked_client, 503).status_code == 503
        restarted = FakeDownloaderServer(
            [{"id": 1001, "state": downloader_state(9)}], database_path, port=fake_downloader.port
        )
        try:
            assert wait_for_link(linked_client, 200).status_code == 200
            states = progress(websocket, 1001, 2)
        finally:
            restarted.stop()

    assert states[0]["complete"] is None
    assert states[1]["messages_count"] == 9


def test_lost_downloader_leaves_no_download_status(
    linked_client: TestClient, fake_downloader: FakeDownloaderServer
) -> None:
    with linked_client.websocket_connect("/api/ws_jsonrpc") as websocket:
        list_chats(websocket)
        fake_downloader.stop()
        states = progress(websocket, 1001, 1)
        chats = list_chats(websocket)

    assert states == [
        {
            "messages_count": 0,
            "oldest_message_date": None,
            "newest_message_date": None,
            "files_count": 0,
            "files_pending": 0,
            "downloaded": False,
            "complete": None,
        }
    ]
    assert next(chat for chat in chats if chat["id"] == 1001)["state"]["complete"] is None
