import asyncio
import json
import logging
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from telethon.tl.types import MessageMediaPhoto
from websockets.asyncio.client import connect

from dossier.database import create_database_engine
from dossier.downloader.__main__ import main, run
from dossier.models import Chat, Message
from tests.downloader.fakes import FakeClient, make_dialog, make_message
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


def photo_event(message_id: int) -> SimpleNamespace:
    message = make_message(-2001, message_id, media=MessageMediaPhoto(photo=None))
    return SimpleNamespace(chat_id=-2001, message=message, is_private=False, is_group=True)


async def test_settings_notice_makes_the_downloader_read_media_settings_again(tmp_path: Path) -> None:
    port = free_port()
    database_path = tmp_path / "messages.db"
    migrate(f"sqlite:///{database_path}")
    engine = create_database_engine(f"sqlite:///{database_path}")
    clients: list[FakeClient] = []

    async def receive_photos_around_a_settings_notice() -> None:
        handle = clients[0].handlers[0]
        async with connect(f"ws://127.0.0.1:{port}/") as api:
            await asyncio.wait_for(api.recv(), timeout=2)
            await handle(photo_event(2))
            with Session(engine) as session, session.begin():
                session.execute(update(Chat).where(Chat.chat_id == -2001).values(download_media=True))
            await handle(photo_event(3))
            await api.send(json.dumps({"jsonrpc": "2.0", "method": "settings_changed", "params": {"id": -2001}}))
            await asyncio.sleep(0.2)
            await handle(photo_event(4))

    clients.append(
        FakeClient(
            dialogs=[make_dialog(-2001, "Family", "group", 1)],
            histories={-2001: [make_message(-2001, 1, media=MessageMediaPhoto(photo=None))]},
            while_running=receive_photos_around_a_settings_notice,
        )
    )

    await run(lambda: clients[0], database_path, tmp_path / "downloads", port)

    with Session(engine) as session:
        media_types = session.execute(
            select(Message.message_id, Message.media_type).where(Message.chat_id == -2001).order_by(Message.message_id)
        ).all()
    assert [tuple(row) for row in media_types] == [(1, None), (2, None), (3, None), (4, "photo")]


def test_missing_key_exits_with_a_message(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    for key in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_PHONE"):
        monkeypatch.delenv(key, raising=False)

    with caplog.at_level(logging.ERROR):
        code = main(["run"])

    assert code == 1
    assert "TELEGRAM_API_ID is not set in .env" in caplog.messages
