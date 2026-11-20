from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from dossier.database import create_database_engine
from dossier.downloader.downloader import Downloader
from dossier.models import Chat
from tests.downloader.fakes import (
    FakeClient,
    RecordingApi,
    make_dialog,
    make_history,
    start,
    store_chat,
    stored_message_ids,
)
from tests.migrate import migrate


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)
    return engine


def downloaded(engine: Engine, chat_id: int) -> bool:
    with Session(engine) as session:
        return session.get_one(Chat, chat_id).downloaded


async def test_newer_messages_download_before_older_messages(engine: Engine, tmp_path: Path) -> None:
    store_chat(engine, -2001, range(200, 301), downloaded=False)
    order: list[int] = []
    client = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 400)],
        histories={-2001: make_history(-2001, 400)},
        before_message=lambda message: order.append(message.id),
    )
    api = RecordingApi()

    await start(Downloader(client, engine, tmp_path / "downloads", api))

    assert order == list(range(301, 401)) + list(range(199, 0, -1))
    assert stored_message_ids(engine, -2001) == list(range(1, 401))
    assert api.states_of(-2001)[-1]["complete"] is True


async def test_chat_stored_from_its_first_live_message_gets_its_older_history(engine: Engine, tmp_path: Path) -> None:
    store_chat(engine, -1000000005001, range(3328, 3401), downloaded=False)
    client = FakeClient(
        dialogs=[make_dialog(-1000000005001, "Big Group", "group", 3400)],
        histories={-1000000005001: make_history(-1000000005001, 3400)},
    )
    api = RecordingApi()

    await start(Downloader(client, engine, tmp_path / "downloads", api))

    assert client.history_requests == [(-1000000005001, "before", 3328)]
    assert stored_message_ids(engine, -1000000005001) == list(range(1, 3401))
    assert downloaded(engine, -1000000005001)
    states = api.states_of(-1000000005001)
    assert (states[0]["complete"], states[-1]["complete"]) == (False, True)


async def test_database_from_the_previous_version_checks_the_older_history_once(engine: Engine, tmp_path: Path) -> None:
    store_chat(engine, -2001, range(1, 501), downloaded=False)
    client = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 500)], histories={-2001: make_history(-2001, 500)}
    )
    api = RecordingApi()

    await start(Downloader(client, engine, tmp_path / "downloads", api))

    assert client.history_requests == [(-2001, "before", 1)]
    assert downloaded(engine, -2001)
    assert api.states_of(-2001)[-1]["complete"] is True


async def test_stop_during_the_older_download_leaves_no_gap(engine: Engine, tmp_path: Path) -> None:
    store_chat(engine, -2001, range(3000, 3401), downloaded=False)

    def stop_at_message_1999(message: SimpleNamespace) -> None:
        if message.id == 1999:
            raise RuntimeError("The downloader stops")

    first_run = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 3400)],
        histories={-2001: make_history(-2001, 3400)},
        before_message=stop_at_message_1999,
    )
    await start(Downloader(first_run, engine, tmp_path / "downloads", RecordingApi()))
    assert stored_message_ids(engine, -2001) == list(range(2000, 3401))
    second_run = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 3400)], histories={-2001: make_history(-2001, 3400)}
    )

    await start(Downloader(second_run, engine, tmp_path / "downloads", RecordingApi()))

    assert second_run.history_requests == [(-2001, "before", 2000)]
    assert stored_message_ids(engine, -2001) == list(range(1, 3401))


async def test_new_chat_downloads_newest_first_and_is_marked_downloaded(engine: Engine, tmp_path: Path) -> None:
    order: list[int] = []
    client = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 5)],
        histories={-2001: make_history(-2001, 5)},
        before_message=lambda message: order.append(message.id),
    )
    await start(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))
    second_run = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 5)], histories={-2001: make_history(-2001, 5)}
    )

    await start(Downloader(second_run, engine, tmp_path / "downloads", RecordingApi()))

    assert order == [5, 4, 3, 2, 1]
    assert client.history_requests == [(-2001, "before", 0)]
    assert downloaded(engine, -2001)
    assert second_run.history_requests == []
