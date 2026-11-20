from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
import socket
import sqlite3

import pytest
from sqlalchemy.orm import Session

from dossier import models
from dossier.backend.openclaw import (
    OpenClawError,
    OpenClawSettings,
    export_chat,
    load_openclaw_settings,
    session_url,
    submit,
)
from dossier.database import create_database_engine
from tests.backend.fake_gateway import FakeGateway
from tests.migrate import migrate


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "messages.db"
    migrate(f"sqlite:///{path}")
    engine = create_database_engine(f"sqlite:///{path}")
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                models.Chat(chat_id=-2001, name="Family", type="group", download_media=False),
                models.Chat(chat_id=-2002, name="Work", type="group", download_media=False),
                models.Chat(chat_id=1001, name="Alice Smith", type="user", download_media=False),
                models.User(user_id=77, first_name="Ann", is_bot=False),
                models.User(user_id=78, first_name="Ben", is_bot=False),
                models.User(user_id=79, first_name="Cid", is_bot=False),
                models.User(user_id=1001, first_name="Alice", is_bot=False),
                models.MessageVersion(
                    chat_id=-2001, message_id=1, version_date="2024-01-01T10:00:00+00:00", text="old", has_media=False
                ),
            ]
        )
        for chat_id, senders in ((-2001, (77, 78, 78)), (-2002, (79, 79, 79)), (1001, (None,))):
            for message_id, sender_id in enumerate(senders, 1):
                session.add(
                    models.Message(
                        chat_id=chat_id,
                        message_id=message_id,
                        date=f"2024-01-0{message_id}T10:00:00+00:00",
                        text=f"message {message_id}",
                        sender_id=sender_id,
                        has_media=False,
                    )
                )
    engine.dispose()
    return path


@pytest.fixture
def gateway() -> Iterator[FakeGateway]:
    server = FakeGateway()
    yield server
    server.stop()


def rows(path: Path, query: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(path) as connection:
        return connection.execute(query).fetchall()


def settings(url: str, agent_id: str = "") -> OpenClawSettings:
    return OpenClawSettings(url, "secret", agent_id, PurePosixPath("/home/me/.openclaw/workspace/dossier"))


def test_group_export_holds_only_the_chat(database_path: Path, tmp_path: Path) -> None:
    path = export_chat(database_path, tmp_path, -2001, datetime(2026, 5, 22, 10, 30, tzinfo=UTC))

    assert path.name == "-2001-2026-05-22_10-30-00.sqlite"
    assert rows(path, "SELECT chat_id FROM chats") == [(-2001,)]
    assert rows(path, "SELECT chat_id, message_id FROM messages ORDER BY message_id") == [
        (-2001, 1),
        (-2001, 2),
        (-2001, 3),
    ]
    assert rows(path, "SELECT user_id FROM users ORDER BY user_id") == [(77,), (78,)]


def test_private_chat_export_holds_the_user_of_the_chat(database_path: Path, tmp_path: Path) -> None:
    path = export_chat(database_path, tmp_path, 1001, datetime(2026, 5, 22, 10, 30, tzinfo=UTC))

    assert rows(path, "SELECT user_id FROM users") == [(1001,)]


def test_export_holds_earlier_versions(database_path: Path, tmp_path: Path) -> None:
    path = export_chat(database_path, tmp_path, -2001, datetime(2026, 5, 22, 10, 30, tzinfo=UTC))

    assert rows(path, "SELECT message_id, text FROM message_versions") == [(1, "old")]


def test_request_admitted_names_the_chat_and_the_file(gateway: FakeGateway) -> None:
    file_path = PurePosixPath("/home/me/.openclaw/workspace/dossier/-2001-2026-05-22_10-30-00.sqlite")

    run_id = submit(
        settings(gateway.url),
        "Summarize the decisions",
        "Family",
        -2001,
        file_path,
        "dossier:-2001:2026-05-22_10-30-00",
    )

    path, headers, body = gateway.requests[0]
    assert run_id == "run-1"
    assert path == "/hooks/agent"
    assert headers["Authorization"] == "Bearer secret"
    assert headers["Idempotency-Key"]
    assert body["name"] == "Dossier"
    assert (body["sessionMode"], body["sessionKey"], body["deliver"]) == (
        "persistent",
        "dossier:-2001:2026-05-22_10-30-00",
        False,
    )
    assert "agentId" not in body
    assert body["message"].startswith("Summarize the decisions\n\n")
    assert '"Family" (id -2001)' in body["message"]
    assert str(file_path) in body["message"]


def test_agent_selected(gateway: FakeGateway) -> None:
    submit(settings(gateway.url, "research"), "Hi", "Family", -2001, PurePosixPath("/x.sqlite"), "dossier:-2001:t")

    assert gateway.requests[0][2]["agentId"] == "research"


def test_wrong_token_is_rejected() -> None:
    gateway = FakeGateway(status=401)
    try:
        with pytest.raises(OpenClawError, match="^OpenClaw rejected the request: HTTP 401$"):
            submit(settings(gateway.url), "Hi", "Family", -2001, PurePosixPath("/x.sqlite"), "dossier:-2001:t")
    finally:
        gateway.stop()


def test_gateway_down_is_unreachable() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    with pytest.raises(OpenClawError, match="^OpenClaw is unreachable:"):
        submit(
            settings(f"http://127.0.0.1:{port}"), "Hi", "Family", -2001, PurePosixPath("/x.sqlite"), "dossier:-2001:t"
        )


def test_settings_need_url_token_and_folder() -> None:
    environ = {"OPENCLAW_URL": "http://gateway:18789", "OPENCLAW_EXPORT_PATH": "/srv/exports"}

    assert load_openclaw_settings(environ) is None
    assert load_openclaw_settings({**environ, "OPENCLAW_HOOK_TOKEN": "secret"}) == OpenClawSettings(
        "http://gateway:18789", "secret", "", PurePosixPath("/srv/exports")
    )


def test_session_link_opens_the_session_in_the_web_ui() -> None:
    assert (
        session_url(settings("https://openclaw.example.com"), "dossier:-2001:2026-05-22_10-30-00")
        == "https://openclaw.example.com/chat/main/dossier/-2001/2026-05-22_10-30-00"
    )
    assert session_url(settings("https://openclaw.example.com", "research"), "dossier:1:t").startswith(
        "https://openclaw.example.com/chat/research/"
    )
