from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session
from telethon.tl.types import (
    Document,
    DocumentAttributeFilename,
    MessageMediaDocument,
    MessageMediaWebPage,
    WebPageEmpty,
)

from dossier.database import create_database_engine
from dossier.downloader.downloader import Downloader
from dossier.models import Chat, Message
from tests.downloader.fakes import (
    FakeClient,
    RecordingApi,
    download_queued,
    make_dialog,
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


def photo_history(count: int) -> list[SimpleNamespace]:
    return [make_message(-2001, message_id, media=make_photo(message_id)) for message_id in range(1, count + 1)]


async def stored_chat(engine: Engine, tmp_path: Path, history: list[SimpleNamespace]) -> tuple[Downloader, FakeClient]:
    client = FakeClient(dialogs=[make_dialog(-2001, "Family", "group", history[-1].id)], histories={-2001: history})
    downloader = Downloader(client, engine, tmp_path / "downloads", RecordingApi())
    await start(downloader)
    return downloader, client


def set_media(engine: Engine, downloader: Downloader, media: bool) -> None:
    with Session(engine) as session, session.begin():
        session.execute(update(Chat).where(Chat.chat_id == -2001).values(download_media=media))
    downloader.settings_changed(-2001)


def media_rows(engine: Engine) -> Sequence[tuple[int, str | None, str | None]]:
    with Session(engine) as session:
        rows = session.execute(
            select(Message.message_id, Message.media_type, Message.media_path)
            .where(Message.chat_id == -2001)
            .order_by(Message.message_id)
        ).all()
    return [(message_id, media_type, media_path) for message_id, media_type, media_path in rows]


async def test_media_turned_on_for_a_stored_chat_saves_newest_first(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await stored_chat(engine, tmp_path, photo_history(3))

    set_media(engine, downloader, True)
    await download_queued(downloader)

    assert client.downloaded == [3, 2, 1]
    folder = tmp_path / "downloads" / "-2001" / "00" / "00"
    assert media_rows(engine) == [
        (1, "photo", str(folder / "01" / "1" / "photo_1.jpg")),
        (2, "photo", str(folder / "02" / "2" / "photo_2.jpg")),
        (3, "photo", str(folder / "03" / "3" / "photo_3.jpg")),
    ]


async def test_message_stored_again_keeps_its_file(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await stored_chat(engine, tmp_path, photo_history(5))
    set_media(engine, downloader, True)
    await download_queued(downloader)
    before = media_rows(engine)

    await downloader.store_message(client.histories[-2001][4])

    assert media_rows(engine) == before


async def test_media_turned_off_stops_after_the_file_in_progress(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await stored_chat(engine, tmp_path, photo_history(300))

    def media_off_at_message_201(message: SimpleNamespace) -> None:
        if message.id == 201:
            set_media(engine, downloader, False)

    client.before_download = media_off_at_message_201
    set_media(engine, downloader, True)
    await download_queued(downloader)

    assert client.downloaded == list(range(300, 200, -1))
    assert media_rows(engine)[200][2] is not None
    assert media_rows(engine)[199][2] is None


async def test_media_turned_on_again_continues_without_a_repeated_file(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await stored_chat(engine, tmp_path, photo_history(300))

    def media_off_at_message_201(message: SimpleNamespace) -> None:
        if message.id == 201:
            set_media(engine, downloader, False)

    client.before_download = media_off_at_message_201
    set_media(engine, downloader, True)
    await download_queued(downloader)
    client.before_download = None
    client.downloaded.clear()
    client.message_requests.clear()

    set_media(engine, downloader, True)
    await download_queued(downloader)

    assert client.downloaded == list(range(200, 0, -1))
    assert not {*range(201, 301)} & {message_id for ids in client.message_requests for message_id in ids}


async def test_web_page_preview_gets_media_type_other_once(engine: Engine, tmp_path: Path) -> None:
    history = photo_history(9)
    history[8] = make_message(-2001, 9, media=MessageMediaWebPage(webpage=WebPageEmpty(id=1)))
    downloader, client = await stored_chat(engine, tmp_path, history)
    set_media(engine, downloader, True)
    await download_queued(downloader)
    client.message_requests.clear()

    downloader.queue_media(-2001)
    await download_queued(downloader)

    assert media_rows(engine)[8] == (9, "other", None)
    assert client.message_requests == []


async def test_deleted_message_gets_media_type_other(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await stored_chat(engine, tmp_path, photo_history(6))
    client.histories[-2001].pop(5)

    set_media(engine, downloader, True)
    await download_queued(downloader)

    assert media_rows(engine)[5] == (6, "other", None)


async def test_failed_file_download_retries_at_the_next_run(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await stored_chat(engine, tmp_path, photo_history(3))

    def fail_at_message_2(message: SimpleNamespace) -> None:
        if message.id == 2:
            raise RuntimeError("Telegram fails")

    client.before_download = fail_at_message_2
    set_media(engine, downloader, True)
    await download_queued(downloader)

    assert client.downloaded == [3, 1]
    assert media_rows(engine)[1] == (2, None, None)
    client.before_download = None
    downloader.queue_media(-2001)
    await download_queued(downloader)
    assert client.downloaded == [3, 1, 2]


async def test_media_progress_reports_after_every_10_files(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await stored_chat(engine, tmp_path, photo_history(25))
    api = RecordingApi()
    downloader.api = api

    set_media(engine, downloader, True)
    await download_queued(downloader)

    assert [(state["files_count"], state["files_pending"]) for state in api.states_of(-2001)] == [
        (10, 15),
        (20, 5),
        (25, 0),
    ]


async def test_media_off_reports_all_files_pending(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await stored_chat(engine, tmp_path, photo_history(25))

    state = downloader.state(-2001)

    assert (state["files_count"], state["files_pending"]) == (0, 25)


async def test_document_named_with_a_folder_loses_the_folder(engine: Engine, tmp_path: Path) -> None:
    document = Document(
        id=12,
        access_hash=0,
        file_reference=b"",
        date=None,
        mime_type="image/jpeg",
        size=5,
        dc_id=2,
        attributes=[DocumentAttributeFilename(file_name="photos/trip.jpg")],
    )
    history = photo_history(11) + [make_message(-2001, 12, media=MessageMediaDocument(document=document))]
    downloader, client = await stored_chat(engine, tmp_path, history)

    set_media(engine, downloader, True)
    await download_queued(downloader)

    assert media_rows(engine)[11][2] == str(tmp_path / "downloads" / "-2001" / "00" / "00" / "12" / "12" / "trip.jpg")


async def test_lost_settings_notice_applies_at_the_next_check(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await stored_chat(engine, tmp_path, photo_history(3))
    with Session(engine) as session, session.begin():
        session.execute(update(Chat).where(Chat.chat_id == -2001).values(download_media=True))

    await downloader.check()
    await download_queued(downloader)

    assert client.downloaded == [3, 2, 1]


async def test_check_with_nothing_to_do_reads_only_the_dialog_list(engine: Engine, tmp_path: Path) -> None:
    downloader, client = await stored_chat(engine, tmp_path, photo_history(3))
    requests = list(client.history_requests)

    await downloader.check()
    await download_queued(downloader)

    assert client.dialog_reads == 2
    assert client.history_requests == requests
    assert (client.message_requests, client.downloaded) == ([], [])
