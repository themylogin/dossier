from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session
from telethon import events

from dossier.database import create_database_engine
from dossier.downloader.downloader import Downloader
from dossier.models import Chat, Message, MessageVersion
from tests.downloader.fakes import (
    FakeClient,
    RecordingApi,
    download_queued,
    make_dialog,
    make_history,
    make_message,
    make_photo,
    start,
)
from tests.migrate import migrate


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)
    return engine


def at(hour: int, minute: int) -> datetime:
    return datetime(2026, 5, 22, hour, minute, tzinfo=UTC)


async def started(engine: Engine, tmp_path: Path, history: list[SimpleNamespace]) -> tuple[Downloader, FakeClient]:
    client = FakeClient(dialogs=[make_dialog(-2001, "Family", "group", history[-1].id)], histories={-2001: history})
    downloader = Downloader(client, engine, tmp_path / "downloads", RecordingApi())
    await start(downloader)
    return downloader, client


async def edit(client: FakeClient, message: SimpleNamespace) -> None:
    client.histories[-2001][message.id - 1] = message
    await client.handler(events.MessageEdited)(SimpleNamespace(chat_id=-2001, message=message))


def stored(engine: Engine, message_id: int) -> tuple[str, str | None, str | None]:
    with Session(engine) as session:
        row = session.scalars(select(Message).where(Message.chat_id == -2001, Message.message_id == message_id)).one()
    return row.text, row.edit_date, row.media_path


def versions(engine: Engine) -> Sequence[tuple[str, str, str | None]]:
    with Session(engine) as session:
        rows = session.execute(
            select(MessageVersion.text, MessageVersion.version_date, MessageVersion.media_path).order_by(
                MessageVersion.version_date
            )
        ).all()
    return [(text, version_date, media_path) for text, version_date, media_path in rows]


def set_media(engine: Engine, downloader: Downloader, media: bool) -> None:
    with Session(engine) as session, session.begin():
        session.execute(update(Chat).where(Chat.chat_id == -2001).values(download_media=media))
    downloader.settings_changed(-2001)


def text_history() -> list[SimpleNamespace]:
    return make_history(-2001, 4) + [make_message(-2001, 5, text="A")]


def photo_history() -> list[SimpleNamespace]:
    return [make_message(-2001, message_id, media=make_photo(message_id)) for message_id in range(1, 6)]


async def test_text_edit_moves_the_earlier_version(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await started(engine, tmp_path, text_history())

    await edit(client, make_message(-2001, 5, text="B", edit_date=at(10, 30)))

    assert stored(engine, 5) == ("B", "2026-05-22T10:30:00+00:00", None)
    assert versions(engine) == [("A", "2024-01-01T00:05:00+00:00", None)]


async def test_two_edits_keep_both_earlier_versions(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await started(engine, tmp_path, text_history())

    await edit(client, make_message(-2001, 5, text="B", edit_date=at(10, 30)))
    await edit(client, make_message(-2001, 5, text="C", edit_date=at(11, 0)))

    assert stored(engine, 5)[0] == "C"
    assert [text for text, _, _ in versions(engine)] == ["A", "B"]


async def test_same_version_again_changes_nothing(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await started(engine, tmp_path, text_history())
    await edit(client, make_message(-2001, 5, text="B", edit_date=at(10, 30)))

    await edit(client, make_message(-2001, 5, text="B", edit_date=at(10, 30)))

    assert stored(engine, 5) == ("B", "2026-05-22T10:30:00+00:00", None)
    assert len(versions(engine)) == 1


async def test_edit_of_a_message_that_is_not_stored_is_ignored(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await started(engine, tmp_path, text_history())

    await client.handler(events.MessageEdited)(
        SimpleNamespace(chat_id=-2001, message=make_message(-2001, 150, text="B", edit_date=at(10, 30)))
    )

    assert versions(engine) == []


async def test_edit_replayed_after_a_restart_is_stored(engine: Engine, tmp_path: Path) -> None:
    await started(engine, tmp_path, text_history())
    downloader, client = await started(engine, tmp_path, text_history())

    await edit(client, make_message(-2001, 5, text="B", edit_date=at(10, 30)))

    assert stored(engine, 5)[0] == "B"
    assert [text for text, _, _ in versions(engine)] == ["A"]


async def test_caption_edit_keeps_the_file(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await started(engine, tmp_path, photo_history())
    set_media(engine, downloader, True)
    await download_queued(downloader)
    path = stored(engine, 5)[2]

    await edit(client, make_message(-2001, 5, media=make_photo(5), text="caption", edit_date=at(10, 30)))
    await download_queued(downloader)

    assert stored(engine, 5) == ("caption", "2026-05-22T10:30:00+00:00", path)
    assert client.downloaded == [5, 4, 3, 2, 1]


async def test_replaced_photo_gets_its_own_folder(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await started(engine, tmp_path, photo_history())
    set_media(engine, downloader, True)
    await download_queued(downloader)
    folder = tmp_path / "downloads" / "-2001" / "00" / "00" / "05" / "5"

    await edit(client, make_message(-2001, 5, media=make_photo(500), edit_date=at(10, 30)))
    await download_queued(downloader)

    assert stored(engine, 5)[2] == str(folder / "2026-05-22_10-30-00" / "photo_5.jpg")
    assert versions(engine)[0][2] == str(folder / "photo_5.jpg")
    assert (folder / "photo_5.jpg").exists()


async def test_photo_replaced_while_media_is_off_saves_the_new_photo_only(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await started(engine, tmp_path, photo_history())

    await edit(client, make_message(-2001, 5, media=make_photo(500), edit_date=at(10, 30)))
    set_media(engine, downloader, True)
    await download_queued(downloader)

    assert client.downloaded == [5, 4, 3, 2, 1]
    assert stored(engine, 5)[2] is not None
    assert "2026-05-22_10-30-00" in str(stored(engine, 5)[2])
    assert versions(engine)[0][2] is None
