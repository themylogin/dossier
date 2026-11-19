import time
from datetime import UTC, datetime
from itertools import pairwise

from tests.rpc import list_chats, progress, request, wait_until_all_complete


def test_full_simulated_download(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chat_id = list_chats(websocket)[0]["id"]
        started = datetime.now(UTC).replace(microsecond=0)
        request(websocket, "update_chat", {"id": chat_id, "settings": {"media": False}}, request_id=2)
        states = progress(websocket, chat_id, 10)
        finished = datetime.now(UTC)
        time.sleep(0.1)
        _, before_reply = request(websocket, "list_chats", request_id=3)

    oldest = {state["oldest_message_date"] for state in states}
    newest = [datetime.fromisoformat(state["newest_message_date"]) for state in states]
    assert [state["messages_count"] for state in states] == [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    assert len(oldest) == 1
    assert datetime.fromisoformat(oldest.pop()) < newest[0]
    assert all(earlier < later for earlier, later in pairwise(newest))
    assert started <= newest[-1] <= finished
    assert [state["complete"] for state in states] == [False] * 9 + [True]
    assert not [
        message
        for message in before_reply
        if message.get("method") == "chat_download_progress" and message["params"]["id"] == chat_id
    ]


def test_dates_carry_an_offset(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chat_id = list_chats(websocket)[0]["id"]
        request(websocket, "update_chat", {"id": chat_id, "settings": {"media": False}}, request_id=2)
        states = progress(websocket, chat_id, 10)

    dates = [state[key] for state in states for key in ("oldest_message_date", "newest_message_date")]
    assert all(datetime.fromisoformat(date).tzinfo is not None for date in dates)


def test_all_chats_download_at_start(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chats = wait_until_all_complete(websocket)

    assert all(chat["state"]["complete"] for chat in chats)
    assert all(chat["state"]["messages_count"] == 1000 for chat in chats)


def test_two_clients_get_the_same_progress(client):
    with (
        client.websocket_connect("/api/ws_jsonrpc") as first,
        client.websocket_connect("/api/ws_jsonrpc") as second,
    ):
        wait_until_all_complete(first)
        chat_id = list_chats(second)[0]["id"]
        request(first, "update_chat", {"id": chat_id, "settings": {"media": True}}, request_id=2)
        first_states = progress(first, chat_id, 10)
        second_states = progress(second, chat_id, 10)

    assert first_states == second_states
    assert second_states[-1]["complete"]


def test_a_closed_client_does_not_stop_progress_for_others(client):
    with client.websocket_connect("/api/ws_jsonrpc") as staying:
        with client.websocket_connect("/api/ws_jsonrpc") as leaving:
            wait_until_all_complete(leaving)
        chat_id = list_chats(staying)[0]["id"]
        request(staying, "update_chat", {"id": chat_id, "settings": {"media": True}}, request_id=2)
        states = progress(staying, chat_id, 10)

    assert [state["messages_count"] for state in states] == [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]


def test_saving_during_a_download_restarts_it(slow_client):
    with slow_client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chat_id = list_chats(websocket)[0]["id"]
        request(websocket, "update_chat", {"id": chat_id, "settings": {"media": True}}, request_id=2)
        before_save = progress(websocket, chat_id, 3)
        reply, _ = request(websocket, "update_chat", {"id": chat_id, "settings": {"media": True}}, request_id=3)
        after_save = progress(websocket, chat_id, 1)

    assert before_save[-1]["messages_count"] == 300
    assert reply["result"]["state"]["messages_count"] == 0
    assert after_save[0]["messages_count"] == 100


def test_saving_after_completion_starts_again(client):
    with client.websocket_connect("/api/ws_jsonrpc") as websocket:
        chat_id = list_chats(websocket)[0]["id"]
        request(websocket, "update_chat", {"id": chat_id, "settings": {"media": True}}, request_id=2)
        first_run = progress(websocket, chat_id, 10)
        reply, _ = request(websocket, "update_chat", {"id": chat_id, "settings": {"media": True}}, request_id=3)
        second_run = progress(websocket, chat_id, 1)

    assert first_run[-1]["complete"]
    assert reply["result"]["state"]["messages_count"] == 0
    assert second_run[0]["messages_count"] == 100
