import asyncio
import json

from websockets.asyncio.client import connect

from dossier.downloader.api import DownloaderApi, DownloadStateJson


def state(messages_count: int, complete: bool) -> DownloadStateJson:
    return {
        "messages_count": messages_count,
        "oldest_message_date": "2024-01-01T10:00:00+00:00",
        "newest_message_date": "2024-01-02T10:00:00+00:00",
        "files_count": 0,
        "files_pending": 0,
        "complete": complete,
    }


async def test_backend_connects_and_first_gets_every_chat() -> None:
    api = DownloaderApi()
    api.states.update({1001: state(10, True), 1002: state(20, False), -2001: state(30, True)})
    connections: list[int] = []

    async with api.serve("127.0.0.1", 0, lambda: connections.append(1), lambda chat_id: None) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}/") as connection:
            first = json.loads(await connection.recv())

    assert connections == [1]
    assert first == {
        "jsonrpc": "2.0",
        "method": "chat_states",
        "params": {
            "chats": [
                {"id": 1001, "state": state(10, True)},
                {"id": 1002, "state": state(20, False)},
                {"id": -2001, "state": state(30, True)},
            ]
        },
    }


async def test_two_connections_get_each_state_change() -> None:
    api = DownloaderApi()

    async with api.serve("127.0.0.1", 0, lambda: None, lambda chat_id: None) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}/") as first, connect(f"ws://127.0.0.1:{port}/") as second:
            await first.recv()
            await second.recv()
            await api.publish(1001, state(100, False))
            first_update = json.loads(await first.recv())
            second_update = json.loads(await second.recv())

    expected = {
        "jsonrpc": "2.0",
        "method": "chat_download_progress",
        "params": {"id": 1001, "state": state(100, False)},
    }
    assert first_update == expected
    assert second_update == expected
    assert api.states == {1001: state(100, False)}


async def test_a_closed_connection_does_not_stop_updates_for_others() -> None:
    api = DownloaderApi()

    async with api.serve("127.0.0.1", 0, lambda: None, lambda chat_id: None) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}/") as staying:
            await staying.recv()
            async with connect(f"ws://127.0.0.1:{port}/") as leaving:
                await leaving.recv()
            await api.publish(1001, state(100, False))
            update = json.loads(await staying.recv())

    assert update["params"] == {"id": 1001, "state": state(100, False)}


async def test_settings_changed_reaches_the_downloader() -> None:
    api = DownloaderApi()
    changed: asyncio.Queue[int] = asyncio.Queue()

    async with api.serve("127.0.0.1", 0, lambda: None, changed.put_nowait) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}/") as connection:
            await connection.recv()
            await connection.send(json.dumps({"jsonrpc": "2.0", "method": "settings_changed", "params": {"id": 1001}}))
            chat_id = await asyncio.wait_for(changed.get(), timeout=2)

    assert chat_id == 1001
