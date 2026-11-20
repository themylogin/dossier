from collections.abc import Sequence
from datetime import UTC, datetime
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from dossier.database import create_database_engine
from dossier.downloader.downloader import Downloader
from dossier.models import Chat, Message
from tests.downloader.fakes import FakeClient, RecordingApi, make_dialog, make_message, make_photo, start
from tests.migrate import migrate


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)
    return engine


def set_media(engine: Engine, chat_id: int, media: bool) -> None:
    with Session(engine) as session, session.begin():
        session.merge(Chat(chat_id=chat_id, name="Family", type="group", tracked=True, download_media=media))


def stored_messages(engine: Engine, chat_id: int) -> Sequence[Message]:
    with Session(engine) as session:
        return session.scalars(select(Message).where(Message.chat_id == chat_id).order_by(Message.message_id)).all()


def photo_message(message_id: int, date: datetime | None = None) -> SimpleNamespace:
    return make_message(-2001, message_id, media=make_photo(message_id), date=date)


async def test_media_off_stores_the_message_without_a_file(engine: Engine, tmp_path: Path) -> None:
    set_media(engine, -2001, False)
    client = FakeClient(dialogs=[make_dialog(-2001, "Family", "group", 1)], histories={-2001: [photo_message(1)]})

    await start(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))

    message = stored_messages(engine, -2001)[0]
    assert (message.has_media, message.media_type, message.media_path) == (True, None, None)
    assert not (tmp_path / "downloads").exists()


async def test_media_on_saves_the_photo_and_its_path(engine: Engine, tmp_path: Path) -> None:
    set_media(engine, -2001, True)
    client = FakeClient(dialogs=[make_dialog(-2001, "Family", "group", 1)], histories={-2001: [photo_message(1)]})

    await start(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))

    message = stored_messages(engine, -2001)[0]
    photo = tmp_path / "downloads" / "-2001" / "00" / "00" / "01" / "1" / "photo_1.jpg"
    assert message.media_type == "photo"
    assert message.media_path == str(photo)
    assert photo.read_bytes() == b"media"


async def test_media_turned_on_during_a_download_applies_to_the_next_messages(engine: Engine, tmp_path: Path) -> None:
    set_media(engine, -2001, False)
    downloaders: list[Downloader] = []

    def turn_media_on_before_message_3(message: SimpleNamespace) -> None:
        if message.id == 3:
            with Session(engine) as session, session.begin():
                session.execute(update(Chat).where(Chat.chat_id == -2001).values(download_media=True))
            downloaders[0].clear_media_cache()

    client = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 4)],
        histories={-2001: [photo_message(message_id) for message_id in range(1, 5)]},
        before_message=turn_media_on_before_message_3,
    )
    downloaders.append(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))

    await start(downloaders[0])

    assert [message.media_type for message in stored_messages(engine, -2001)] == ["photo"] * 4


async def test_dialog_stored_again_keeps_media_on(engine: Engine, tmp_path: Path) -> None:
    set_media(engine, -2001, True)
    client = FakeClient(dialogs=[make_dialog(-2001, "Family renamed", "group", 0)])

    await start(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))

    with Session(engine) as session:
        chat = session.get_one(Chat, -2001)
    assert (chat.name, chat.download_media) == ("Family renamed", True)


async def test_new_chat_starts_with_media_off(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient(dialogs=[make_dialog(-2002, "Book Club", "group", 0)])

    await start(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))

    with Session(engine) as session:
        assert session.get_one(Chat, -2002).download_media is False


async def test_photo_of_message_7890_gets_the_bot_py_path_and_date(engine: Engine, tmp_path: Path) -> None:
    set_media(engine, -2001, True)
    sent = datetime(2026, 5, 22, 10, 30, tzinfo=UTC)
    client = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 7890)], histories={-2001: [photo_message(7890, sent)]}
    )

    await start(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))

    photo = tmp_path / "downloads" / "-2001" / "00" / "78" / "90" / "7890" / "photo_7890.jpg"
    assert photo.exists()
    assert os.stat(photo).st_mtime == sent.timestamp()
