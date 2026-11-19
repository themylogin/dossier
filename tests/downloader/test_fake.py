import asyncio
from datetime import UTC, datetime
from itertools import pairwise
import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session
from websockets.asyncio.client import ClientConnection, connect

from dossier.database import create_database_engine
from dossier.downloader.api import DownloaderApi
from dossier.downloader.fake import FakeDownloader
from dossier.models import Chat
from tests.migrate import migrate


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)
    return engine


async def notices_for(connection: ClientConnection, chat_id: int, count: int) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    while len(states) < count:
        message = json.loads(await asyncio.wait_for(connection.recv(), timeout=5))
        if message["method"] == "chat_download_progress" and message["params"]["id"] == chat_id:
            states.append(message["params"]["state"])
    return states


async def settings_changed(connection: ClientConnection, chat_id: int) -> None:
    await connection.send(json.dumps({"jsonrpc": "2.0", "method": "settings_changed", "params": {"id": chat_id}}))


def test_first_start_stores_private_chats_and_groups_with_media_off(engine: Engine) -> None:
    FakeDownloader(engine, DownloaderApi(), 0.01).store_chats()

    with Session(engine) as session:
        chats = session.execute(select(Chat.chat_id, Chat.download_media)).all()
    assert any(chat_id > 0 for chat_id, media in chats)
    assert any(chat_id < 0 for chat_id, media in chats)
    assert all(media is False for chat_id, media in chats)


def test_later_start_keeps_the_stored_setting(engine: Engine) -> None:
    FakeDownloader(engine, DownloaderApi(), 0.01).store_chats()
    with Session(engine) as session, session.begin():
        session.execute(update(Chat).where(Chat.chat_id == 1001).values(download_media=True))

    FakeDownloader(engine, DownloaderApi(), 0.01).store_chats()

    with Session(engine) as session:
        assert session.get_one(Chat, 1001).download_media is True


async def test_all_chats_download_at_start(engine: Engine) -> None:
    api = DownloaderApi()
    fake_downloader = FakeDownloader(engine, api, 0.01)

    for chat_id in fake_downloader.chats:
        fake_downloader.start(chat_id)
    await asyncio.gather(*fake_downloader.tasks.values())

    assert all(state["complete"] and state["messages_count"] == 1000 for state in api.states.values())
    assert set(api.states) == set(fake_downloader.chats)


async def test_settings_saved_reports_the_zero_state_at_once(engine: Engine) -> None:
    api = DownloaderApi()
    fake_downloader = FakeDownloader(engine, api, 0.01)

    async with api.serve("127.0.0.1", 0, lambda: None, fake_downloader.start) as server:
        async with connect(f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/") as connection:
            await connection.recv()
            await settings_changed(connection, 1001)
            first = (await notices_for(connection, 1001, 1))[0]
        await fake_downloader.close()

    assert first == {"messages_count": 0, "oldest_message_date": None, "newest_message_date": None, "complete": False}


async def test_settings_saved_again_during_a_download_restarts_it(engine: Engine) -> None:
    api = DownloaderApi()
    fake_downloader = FakeDownloader(engine, api, 0.2)

    async with api.serve("127.0.0.1", 0, lambda: None, fake_downloader.start) as server:
        async with connect(f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/") as connection:
            await connection.recv()
            await settings_changed(connection, 1001)
            before = await notices_for(connection, 1001, 4)
            await settings_changed(connection, 1001)
            after = await notices_for(connection, 1001, 2)
        await fake_downloader.close()

    assert before[-1]["messages_count"] == 300
    assert [state["messages_count"] for state in after] == [0, 100]


async def test_settings_saved_again_after_completion_starts_again(engine: Engine) -> None:
    api = DownloaderApi()
    fake_downloader = FakeDownloader(engine, api, 0.01)

    async with api.serve("127.0.0.1", 0, lambda: None, fake_downloader.start) as server:
        async with connect(f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/") as connection:
            await connection.recv()
            await settings_changed(connection, 1001)
            first_run = await notices_for(connection, 1001, 11)
            await settings_changed(connection, 1001)
            second_run = await notices_for(connection, 1001, 2)
        await fake_downloader.close()

    assert first_run[-1]["complete"] is True
    assert [state["messages_count"] for state in second_run] == [0, 100]


async def test_full_simulated_download(engine: Engine) -> None:
    api = DownloaderApi()
    fake_downloader = FakeDownloader(engine, api, 0.01)

    async with api.serve("127.0.0.1", 0, lambda: None, fake_downloader.start) as server:
        async with connect(f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}/") as connection:
            await connection.recv()
            started = datetime.now(UTC).replace(microsecond=0)
            await settings_changed(connection, -2001)
            states = (await notices_for(connection, -2001, 11))[1:]
            finished = datetime.now(UTC)
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(connection.recv(), timeout=0.2)
        await fake_downloader.close()

    oldest = {state["oldest_message_date"] for state in states}
    newest = [datetime.fromisoformat(state["newest_message_date"]) for state in states]
    assert [state["messages_count"] for state in states] == [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    assert len(oldest) == 1
    assert datetime.fromisoformat(oldest.pop()) < newest[0]
    assert all(earlier < later for earlier, later in pairwise(newest))
    assert started <= newest[-1] <= finished
    assert [state["complete"] for state in states] == [False] * 9 + [True]
