import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Engine
from telethon import events

from dossier.database import create_database_engine
from dossier.downloader.api import DownloadStateJson
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


def new_message_event(chat_id: int, message: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(chat_id=chat_id, message=message)


async def test_message_arrives_through_a_history_request(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient(dialogs=[make_dialog(-2001, "Family", "group", 40)], histories={-2001: make_history(-2001, 40)})
    api = RecordingApi()
    downloader = Downloader(client, engine, tmp_path / "downloads", api)
    await start(downloader)
    sent = datetime(2026, 5, 22, 10, 30, tzinfo=UTC)
    client.histories[-2001].append(make_message(-2001, 41, date=sent))

    await client.handler(events.NewMessage)(new_message_event(-2001, client.histories[-2001][-1]))
    await download_queued(downloader)

    assert client.history_requests[-1] == (-2001, "after", 40)
    assert stored_message_ids(engine, -2001) == list(range(1, 42))
    assert api.states_of(-2001)[-1] == {
        "messages_count": 41,
        "oldest_message_date": "2024-01-01T00:01:00+00:00",
        "newest_message_date": "2026-05-22T10:30:00+00:00",
        "files_count": 0,
        "files_pending": 0,
        "downloaded": True,
        "complete": True,
    }


async def test_service_message_before_a_new_message_is_stored_too(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient(dialogs=[make_dialog(-2001, "Family", "group", 40)], histories={-2001: make_history(-2001, 40)})
    api = RecordingApi()
    downloader = Downloader(client, engine, tmp_path / "downloads", api)
    await start(downloader)
    client.histories[-2001] += [make_message(-2001, 41), make_message(-2001, 42)]

    await client.handler(events.NewMessage)(new_message_event(-2001, client.histories[-2001][-1]))
    await download_queued(downloader)

    assert stored_message_ids(engine, -2001) == list(range(1, 43))
    assert (api.states_of(-2001)[-1]["messages_count"], api.states_of(-2001)[-1]["complete"]) == (42, True)


async def test_message_during_the_start_up_download_does_not_wait_for_it(engine: Engine, tmp_path: Path) -> None:
    first_run = FakeClient(
        dialogs=[make_dialog(-2002, "Work", "group", 40)], histories={-2002: make_history(-2002, 40)}
    )
    await start(Downloader(first_run, engine, tmp_path / "downloads", RecordingApi()))

    work_reported_41 = asyncio.Event()

    class WorkApi(RecordingApi):
        async def publish(self, chat_id: int, state: DownloadStateJson) -> None:
            await super().publish(chat_id, state)
            if chat_id == -2002 and state["messages_count"] == 41:
                work_reported_41.set()

    class SlowFamilyClient(FakeClient):
        async def iterate(self, chat_id: int, messages: list[SimpleNamespace]) -> AsyncIterator[SimpleNamespace]:
            if chat_id == -2001 and not self.history_requests[1:]:
                await self.handler(events.NewMessage)(new_message_event(-2002, self.histories[-2002][-1]))
                await asyncio.wait_for(work_reported_41.wait(), timeout=2)
            async for message in super().iterate(chat_id, messages):
                yield message

    second_run = SlowFamilyClient(
        dialogs=[make_dialog(-2001, "Family", "group", 3), make_dialog(-2002, "Work", "group", 40)],
        histories={-2001: make_history(-2001, 3), -2002: make_history(-2002, 41)},
    )
    api = WorkApi()

    await start(Downloader(second_run, engine, tmp_path / "downloads", api))

    assert stored_message_ids(engine, -2001) == [1, 2, 3]
    assert api.states_of(-2002)[-1]["messages_count"] == 41


async def test_message_during_the_last_history_request_gets_one_more_pass(engine: Engine, tmp_path: Path) -> None:
    histories = {-2001: make_history(-2001, 300)}

    async def message_301_arrives(chat_id: int) -> None:
        if len(histories[-2001]) == 300:
            histories[-2001].append(make_message(-2001, 301))
            await client.handler(events.NewMessage)(new_message_event(-2001, histories[-2001][-1]))

    client = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 300)], histories=histories, after_history=message_301_arrives
    )
    api = RecordingApi()

    await start(Downloader(client, engine, tmp_path / "downloads", api))

    assert client.history_requests == [(-2001, "before", 0), (-2001, "after", 300)]
    assert stored_message_ids(engine, -2001) == list(range(1, 302))
    assert (api.states_of(-2001)[-1]["messages_count"], api.states_of(-2001)[-1]["complete"]) == (301, True)


async def test_restart_during_a_download_leaves_no_gap(engine: Engine, tmp_path: Path) -> None:
    def stop_at_message_200(message: SimpleNamespace) -> None:
        if message.id == 200:
            raise RuntimeError("The downloader stops")

    first_run = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 300)],
        histories={-2001: make_history(-2001, 300)},
        before_message=stop_at_message_200,
    )
    await start(Downloader(first_run, engine, tmp_path / "downloads", RecordingApi()))
    for message_id in (301, 302):
        await first_run.handler(events.NewMessage)(new_message_event(-2001, make_message(-2001, message_id)))
    second_run = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 302)], histories={-2001: make_history(-2001, 302)}
    )

    await start(Downloader(second_run, engine, tmp_path / "downloads", RecordingApi()))

    assert second_run.history_requests == [(-2001, "after", 300), (-2001, "before", 201)]
    assert stored_message_ids(engine, -2001) == list(range(1, 303))


async def test_message_after_a_failed_download_waits_for_the_next_check(engine: Engine, tmp_path: Path) -> None:
    def fail_at_message_3(message: SimpleNamespace) -> None:
        if message.id == 3:
            raise RuntimeError("Telegram fails")

    client = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 5)],
        histories={-2001: make_history(-2001, 5)},
        before_message=fail_at_message_3,
    )
    downloader = Downloader(client, engine, tmp_path / "downloads", RecordingApi())
    await start(downloader)
    client.histories[-2001].append(make_message(-2001, 6))

    await client.handler(events.NewMessage)(new_message_event(-2001, client.histories[-2001][-1]))
    await download_queued(downloader)

    assert stored_message_ids(engine, -2001) == [4, 5]
    client.before_message = None
    client.dialogs = [make_dialog(-2001, "Family", "group", 6)]
    await downloader.check()
    await download_queued(downloader)
    assert stored_message_ids(engine, -2001) == [1, 2, 3, 4, 5, 6]
