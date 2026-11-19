from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from telethon.tl.types import Chat as TelegramChat

from dossier.database import create_database_engine
from dossier.downloader.downloader import Downloader
from dossier.models import Chat, Message
from tests.downloader.fakes import FakeClient, RecordingApi, make_dialog, make_history, make_message
from tests.migrate import migrate


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)
    return engine


def new_message_event(
    chat_id: int, message: SimpleNamespace, is_group: bool, chat: TelegramChat | None
) -> SimpleNamespace:
    async def get_chat() -> TelegramChat | None:
        return chat

    return SimpleNamespace(chat_id=chat_id, message=message, is_private=False, is_group=is_group, get_chat=get_chat)


async def test_message_arrives_after_the_start_up_download(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient(dialogs=[make_dialog(-2001, "Family", "group", 40)], histories={-2001: make_history(-2001, 40)})
    api = RecordingApi()
    downloader = Downloader(client, engine, tmp_path / "downloads", api)
    await downloader.start_up()
    downloader.listen()
    sent = datetime(2026, 5, 22, 10, 30, tzinfo=UTC)

    await client.handlers[0](new_message_event(-2001, make_message(-2001, 41, date=sent), True, None))

    with Session(engine) as session:
        stored = session.scalar(select(func.count()).select_from(Message).where(Message.chat_id == -2001))
    assert stored == 41
    assert api.states_of(-2001)[-1] == {
        "messages_count": 41,
        "oldest_message_date": "2024-01-01T00:01:00+00:00",
        "newest_message_date": "2026-05-22T10:30:00+00:00",
        "complete": True,
    }


async def test_message_from_a_new_chat_stores_the_chat_with_media_off(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient()
    api = RecordingApi()
    downloader = Downloader(client, engine, tmp_path / "downloads", api)
    await downloader.start_up()
    downloader.listen()
    chat = TelegramChat(id=3003, title="New Group", photo=None, participants_count=3, date=None, version=1)

    await client.handlers[0](new_message_event(-3003, make_message(-3003, 1), True, chat))

    with Session(engine) as session:
        stored_chat = session.get_one(Chat, -3003)
    assert (stored_chat.name, stored_chat.type, stored_chat.download_media) == ("New Group", "group", False)
    assert api.states_of(-3003)[-1]["complete"] is True
