import asyncio
import json
import logging
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session
from telethon import events
from websockets.asyncio.client import ClientConnection, connect

from dossier.database import create_database_engine
from dossier.downloader.__main__ import main, run
from dossier.models import Chat, Message
from tests.downloader.fakes import FakeClient, make_dialog, make_message, make_photo
from tests.migrate import migrate


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


async def test_not_logged_in_exits_with_the_login_command(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    migrate(f"sqlite:///{tmp_path / 'messages.db'}")
    client = FakeClient(authorized=False)

    with caplog.at_level(logging.ERROR):
        code = await run(lambda: client, tmp_path / "messages.db", tmp_path / "downloads", free_port())

    assert code == 1
    assert "The Telegram session is not logged in. Run: docker compose run --rm downloader login" in caplog.messages
    assert client.calls == ["connect", "disconnect"]


async def test_start_order_is_api_then_telegram(tmp_path: Path) -> None:
    port = free_port()
    migrate(f"sqlite:///{tmp_path / 'messages.db'}")
    first_messages: list[str] = []

    async def check_before_telegram() -> None:
        async with connect(f"ws://127.0.0.1:{port}/") as api:
            first_messages.append(json.loads(await asyncio.wait_for(api.recv(), timeout=2))["method"])

    client = FakeClient(on_connect=check_before_telegram)

    code = await run(lambda: client, tmp_path / "messages.db", tmp_path / "downloads", port)

    assert code == 0
    assert first_messages == ["chat_states"]
    assert client.calls == ["connect", "run_until_disconnected"]


async def wait_until_complete(api: ClientConnection, chat_id: int) -> None:
    snapshot = json.loads(await asyncio.wait_for(api.recv(), timeout=2))
    complete = {chat["id"] for chat in snapshot["params"]["chats"] if chat["state"]["complete"]}
    while chat_id not in complete:
        progress = json.loads(await asyncio.wait_for(api.recv(), timeout=2))["params"]
        if progress["state"]["complete"]:
            complete.add(progress["id"])


def photo_message(message_id: int) -> SimpleNamespace:
    return make_message(-2001, message_id, media=make_photo(message_id))


async def wait_until_stored(engine: Engine, message_id: int, with_file: bool) -> None:
    statement = select(Message.media_path).where(Message.chat_id == -2001, Message.message_id == message_id)
    async with asyncio.timeout(5):
        while True:
            with Session(engine) as session:
                row = session.execute(statement).one_or_none()
            if row is not None and (row.media_path is not None or not with_file):
                return
            await asyncio.sleep(0.01)


async def test_settings_notice_starts_the_media_downloads_of_the_chat(tmp_path: Path) -> None:
    port = free_port()
    database_path = tmp_path / "messages.db"
    migrate(f"sqlite:///{database_path}")
    engine = create_database_engine(f"sqlite:///{database_path}")
    client = FakeClient(dialogs=[make_dialog(-2001, "Family", "group", 1)], histories={-2001: [photo_message(1)]})

    async def arrive(message_id: int) -> None:
        client.histories[-2001].append(photo_message(message_id))
        await client.handler(events.NewMessage)(SimpleNamespace(chat_id=-2001, message=client.histories[-2001][-1]))

    async def receive_photos_around_a_settings_notice() -> None:
        async with connect(f"ws://127.0.0.1:{port}/") as api:
            await wait_until_complete(api, -2001)
            await arrive(2)
            await wait_until_stored(engine, 2, with_file=False)
            with Session(engine) as session, session.begin():
                session.execute(update(Chat).where(Chat.chat_id == -2001).values(download_media=True))
            await arrive(3)
            await wait_until_stored(engine, 3, with_file=False)
            await api.send(json.dumps({"jsonrpc": "2.0", "method": "settings_changed", "params": {"id": -2001}}))
            await wait_until_stored(engine, 1, with_file=True)
            await arrive(4)
            await wait_until_stored(engine, 4, with_file=True)

    client.while_running = receive_photos_around_a_settings_notice

    await run(lambda: client, database_path, tmp_path / "downloads", port)

    assert client.downloaded == [3, 2, 1, 4]


def test_missing_key_exits_with_a_message(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    for key in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_PHONE"):
        monkeypatch.delenv(key, raising=False)

    with caplog.at_level(logging.ERROR):
        code = main(["run"])

    assert code == 1
    assert "TELEGRAM_API_ID is not set in .env" in caplog.messages
