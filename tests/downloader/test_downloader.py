from collections.abc import Sequence
from pathlib import Path

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from telethon.tl.types import User

from dossier.database import create_database_engine
from dossier.downloader.downloader import Downloader
from dossier.models import Chat, Message
from dossier.models import User as UserRow
from tests.downloader.fakes import FakeClient, RecordingApi, make_dialog, make_history, make_message
from tests.migrate import migrate


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)
    return engine


def stored_message_ids(engine: Engine, chat_id: int) -> Sequence[int]:
    with Session(engine) as session:
        return session.scalars(
            select(Message.message_id).where(Message.chat_id == chat_id).order_by(Message.message_id)
        ).all()


async def test_three_kinds_of_chats_download_in_full(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient(
        dialogs=[
            make_dialog(1001, "Alice Smith", "user", 3),
            make_dialog(-2001, "Family", "group", 2),
            make_dialog(-1003, "News", "channel", 4),
        ],
        histories={1001: make_history(1001, 3), -2001: make_history(-2001, 2), -1003: make_history(-1003, 4)},
    )
    api = RecordingApi()

    await Downloader(client, engine, tmp_path / "downloads", api).start_up()

    with Session(engine) as session:
        types = dict(session.execute(select(Chat.chat_id, Chat.type)).all())
    assert stored_message_ids(engine, 1001) == [1, 2, 3]
    assert stored_message_ids(engine, -2001) == [1, 2]
    assert stored_message_ids(engine, -1003) == [1, 2, 3, 4]
    assert types == {1001: "user", -2001: "group", -1003: "channel"}
    assert all(api.states_of(chat_id)[-1]["complete"] for chat_id in (1001, -2001, -1003))


async def test_interrupted_download_resumes_after_the_newest_stored_message(engine: Engine, tmp_path: Path) -> None:
    first_run = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 500)], histories={-2001: make_history(-2001, 500)}
    )
    await Downloader(first_run, engine, tmp_path / "downloads", RecordingApi()).start_up()
    second_run = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 800)], histories={-2001: make_history(-2001, 800)}
    )

    await Downloader(second_run, engine, tmp_path / "downloads", RecordingApi()).start_up()

    assert second_run.history_requests == [(-2001, 500)]
    assert stored_message_ids(engine, -2001) == list(range(1, 801))


async def test_chat_up_to_date_completes_without_a_history_request(engine: Engine, tmp_path: Path) -> None:
    first_run = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 10)], histories={-2001: make_history(-2001, 10)}
    )
    await Downloader(first_run, engine, tmp_path / "downloads", RecordingApi()).start_up()
    second_run = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 10)], histories={-2001: make_history(-2001, 10)}
    )
    api = RecordingApi()

    await Downloader(second_run, engine, tmp_path / "downloads", api).start_up()

    assert second_run.history_requests == []
    assert api.states_of(-2001) == [
        {
            "messages_count": 10,
            "oldest_message_date": "2024-01-01T00:01:00+00:00",
            "newest_message_date": "2024-01-01T00:10:00+00:00",
            "complete": True,
        }
    ]


async def test_250_messages_report_at_100_200_and_250(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 250)], histories={-2001: make_history(-2001, 250)}
    )
    api = RecordingApi()

    await Downloader(client, engine, tmp_path / "downloads", api).start_up()

    states = api.states_of(-2001)
    assert [state["messages_count"] for state in states] == [100, 200, 250]
    assert [state["complete"] for state in states] == [False, False, True]


async def test_initial_states_come_from_the_database(engine: Engine, tmp_path: Path) -> None:
    client = FakeClient(dialogs=[make_dialog(-2001, "Family", "group", 3)], histories={-2001: make_history(-2001, 3)})
    await Downloader(client, engine, tmp_path / "downloads", RecordingApi()).start_up()

    states = Downloader(FakeClient(), engine, tmp_path / "downloads", RecordingApi()).initial_states()

    assert states == {
        -2001: {
            "messages_count": 3,
            "oldest_message_date": "2024-01-01T00:01:00+00:00",
            "newest_message_date": "2024-01-01T00:03:00+00:00",
            "complete": False,
        }
    }


async def test_message_with_a_new_sender_stores_the_user(engine: Engine, tmp_path: Path) -> None:
    message = make_message(-2001, 1)
    message.sender_id = 77
    message.sender = User(id=77, first_name="Ann", username="ann", bot=False)
    client = FakeClient(dialogs=[make_dialog(-2001, "Family", "group", 1)], histories={-2001: [message]})

    await Downloader(client, engine, tmp_path / "downloads", RecordingApi()).start_up()

    with Session(engine) as session:
        user = session.get_one(UserRow, 77)
    assert (user.first_name, user.username) == ("Ann", "ann")
