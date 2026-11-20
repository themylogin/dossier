from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Engine

from dossier.database import create_database_engine
from dossier.downloader.downloader import Downloader
from tests.downloader.fakes import (
    FakeClient,
    RecordingApi,
    download_queued,
    make_dialog,
    make_history,
    make_message,
    start,
    stored_message_ids,
)
from tests.migrate import migrate


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)
    return engine


async def test_service_message_at_the_top_is_stored_at_the_next_check(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient(dialogs=[make_dialog(-2001, "Family", "group", 40)], histories={-2001: make_history(-2001, 40)})
    api = RecordingApi()
    downloader = Downloader(client, engine, tmp_path / "downloads", api)
    await start(downloader)
    client.histories[-2001].append(make_message(-2001, 41))
    client.dialogs = [make_dialog(-2001, "Family", "group", 41)]

    await downloader.check()
    await download_queued(downloader)

    assert client.history_requests[-1] == (-2001, "after", 40)
    assert stored_message_ids(engine, -2001) == list(range(1, 42))
    assert (api.states_of(-2001)[-1]["messages_count"], api.states_of(-2001)[-1]["complete"]) == (41, True)


async def test_missed_join_downloads_at_the_next_check(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient()
    api = RecordingApi()
    downloader = Downloader(client, engine, tmp_path / "downloads", api)
    await start(downloader)
    client.dialogs.append(make_dialog(-3003, "Book Club", "group", 50))
    client.histories[-3003] = make_history(-3003, 50)

    await downloader.check()
    await download_queued(downloader)

    assert stored_message_ids(engine, -3003) == list(range(1, 51))
    assert api.states_of(-3003)[-1]["complete"] is True


async def test_failed_download_retries_at_the_next_check(engine: Engine, tmp_path: Path) -> None:
    def fail_at_message_3(message: SimpleNamespace) -> None:
        if message.id == 3:
            raise RuntimeError("Telegram fails")

    client = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 5)],
        histories={-2001: make_history(-2001, 5)},
        before_message=fail_at_message_3,
    )
    api = RecordingApi()
    downloader = Downloader(client, engine, tmp_path / "downloads", api)
    await start(downloader)
    client.before_message = None

    await downloader.check()
    await download_queued(downloader)

    assert (-2001, "after", 2) in client.history_requests
    assert stored_message_ids(engine, -2001) == [1, 2, 3, 4, 5]
    assert api.states_of(-2001)[-1]["complete"] is True
