from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from telethon import events
from telethon.tl.types import UpdateChannel

from dossier.database import create_database_engine
from dossier.downloader.downloader import Downloader
from dossier.models import Chat
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


async def test_channel_joined_in_the_main_app_downloads_in_full(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient()
    api = RecordingApi()
    downloader = Downloader(client, engine, tmp_path / "downloads", api)
    await start(downloader)
    client.dialogs.append(make_dialog(-1000000005001, "News", "channel", 300))
    client.histories[-1000000005001] = make_history(-1000000005001, 300)

    await client.handler(events.Raw)(UpdateChannel(channel_id=5001))
    await download_queued(downloader)

    with Session(engine) as session:
        channel = session.get_one(Chat, -1000000005001)
    assert (channel.name, channel.type, channel.download_media) == ("News", "channel", False)
    assert client.history_requests == [(-1000000005001, "after", 0), (-1000000005001, "before", 1)]
    assert stored_message_ids(engine, -1000000005001) == list(range(1, 301))
    assert api.states_of(-1000000005001)[-1]["complete"] is True


async def test_group_that_adds_the_account_downloads_in_full(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient()
    api = RecordingApi()
    downloader = Downloader(client, engine, tmp_path / "downloads", api)
    await start(downloader)
    client.dialogs.append(make_dialog(-3003, "Book Club", "group", 50))
    client.histories[-3003] = make_history(-3003, 50)

    await client.handler(events.ChatAction)(SimpleNamespace(chat_id=-3003))
    await download_queued(downloader)

    assert stored_message_ids(engine, -3003) == list(range(1, 51))
    assert api.states_of(-3003)[-1]["complete"] is True


async def test_first_message_of_a_new_private_chat_downloads_the_chat(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient()
    api = RecordingApi()
    downloader = Downloader(client, engine, tmp_path / "downloads", api)
    await start(downloader)
    first_message = make_message(4004, 1)
    client.dialogs.append(make_dialog(4004, "Bob Brown", "user", 1))
    client.histories[4004] = [first_message]

    await client.handler(events.NewMessage)(SimpleNamespace(chat_id=4004, message=first_message))
    await download_queued(downloader)

    with Session(engine) as session:
        chat = session.get_one(Chat, 4004)
    assert (chat.name, chat.type) == ("Bob Brown", "user")
    assert stored_message_ids(engine, 4004) == [1]
    assert (api.states_of(4004)[-1]["messages_count"], api.states_of(4004)[-1]["complete"]) == (1, True)


async def test_channel_joined_during_the_start_up_download_downloads_after_it(engine: Engine, tmp_path: Path) -> None:
    async def join_channel_after_chat_2001(chat_id: int) -> None:
        if chat_id == -2001:
            client.dialogs.append(make_dialog(-1000000005001, "News", "channel", 3))
            client.histories[-1000000005001] = make_history(-1000000005001, 3)
            await client.handler(events.Raw)(UpdateChannel(channel_id=5001))

    client = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 3)],
        histories={-2001: make_history(-2001, 3)},
        after_history=join_channel_after_chat_2001,
    )

    await start(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))

    assert client.history_requests == [
        (-2001, "after", 0),
        (-2001, "before", 1),
        (-1000000005001, "after", 0),
        (-1000000005001, "before", 1),
    ]
    assert stored_message_ids(engine, -1000000005001) == [1, 2, 3]


async def test_change_of_a_tracked_channel_reads_no_dialog_list(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient(
        dialogs=[make_dialog(-1000000005001, "News", "channel", 3)],
        histories={-1000000005001: make_history(-1000000005001, 3)},
    )
    await start(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))

    await client.handler(events.Raw)(UpdateChannel(channel_id=5001))

    assert client.dialog_reads == 1


async def test_channel_outside_the_dialog_list_stores_nothing(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient()
    await start(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))

    await client.handler(events.Raw)(UpdateChannel(channel_id=5002))

    with Session(engine) as session:
        assert session.get(Chat, -1000000005002) is None
    assert client.history_requests == []


async def test_posts_of_a_left_public_channel_cause_one_dialog_read(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient()
    await start(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))
    new_message = client.handler(events.NewMessage)

    await new_message(SimpleNamespace(chat_id=-1000000005003, message=make_message(-1000000005003, 11)))
    await new_message(SimpleNamespace(chat_id=-1000000005003, message=make_message(-1000000005003, 12)))

    assert client.dialog_reads == 2
    assert stored_message_ids(engine, -1000000005003) == []


async def test_left_channel_joined_again_resumes_after_its_stored_messages(engine: Engine, tmp_path: Path) -> None:
    first_run = FakeClient(
        dialogs=[make_dialog(-1000000005003, "Old News", "channel", 10)],
        histories={-1000000005003: make_history(-1000000005003, 10)},
    )
    await start(Downloader(first_run, engine, tmp_path / "downloads", RecordingApi()))
    client = FakeClient(histories={-1000000005003: make_history(-1000000005003, 15)})
    downloader = Downloader(client, engine, tmp_path / "downloads", RecordingApi())
    await start(downloader)
    await client.handler(events.NewMessage)(
        SimpleNamespace(chat_id=-1000000005003, message=make_message(-1000000005003, 14))
    )
    client.dialogs.append(make_dialog(-1000000005003, "Old News", "channel", 15))

    await client.handler(events.Raw)(UpdateChannel(channel_id=5003))
    await download_queued(downloader)

    assert client.dialog_reads == 3
    assert client.history_requests == [(-1000000005003, "after", 10)]
    assert stored_message_ids(engine, -1000000005003) == list(range(1, 16))
