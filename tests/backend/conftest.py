from collections.abc import Iterator
from pathlib import Path
import time

from fastapi.testclient import TestClient
from httpx2 import Response
import pytest
from sqlalchemy.orm import Session

from dossier import models
from dossier.backend.main import create_app
from dossier.database import create_database_engine
from dossier.downloader.api import DownloadStateJson
from tests.backend.fake_downloader import FakeDownloaderServer
from tests.migrate import migrate


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "messages.db"
    database_url = f"sqlite:///{path}"
    migrate(database_url)
    engine = create_database_engine(database_url)
    with Session(engine) as session, session.begin():
        session.add_all(
            [
                models.Chat(chat_id=-2001, name="Family", type="group", download_media=False),
                models.Chat(chat_id=1001, name="Alice Smith", type="user", download_media=False),
            ]
        )
    engine.dispose()
    return path


@pytest.fixture
def client(database_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(f"sqlite:///{database_path}", "ws://127.0.0.1:9")) as test_client:
        yield test_client


def store_messages(database_path: Path, chat_id: int, count: int) -> None:
    engine = create_database_engine(f"sqlite:///{database_path}")
    with Session(engine) as session, session.begin():
        session.add_all(
            models.Message(
                chat_id=chat_id,
                message_id=number,
                date=f"2024-01-0{number}T10:00:00+00:00",
                text=f"message {number}",
                has_media=False,
            )
            for number in range(1, count + 1)
        )
    engine.dispose()


def wait_for_link(client: TestClient, status: int) -> Response:
    deadline = time.monotonic() + 10
    response = client.get("/api/health")
    while response.status_code != status and time.monotonic() < deadline:
        time.sleep(0.1)
        response = client.get("/api/health")
    return response


@pytest.fixture
def fake_downloader(database_path: Path) -> Iterator[FakeDownloaderServer]:
    state: DownloadStateJson = {
        "messages_count": 7,
        "oldest_message_date": "2024-01-01T10:00:00+00:00",
        "newest_message_date": "2024-01-02T10:00:00+00:00",
        "files_count": 0,
        "files_pending": 0,
        "downloaded": False,
        "complete": True,
    }
    server = FakeDownloaderServer([{"id": 1001, "state": state}], database_path)
    yield server
    server.stop()


@pytest.fixture
def linked_client(database_path: Path, fake_downloader: FakeDownloaderServer) -> Iterator[TestClient]:
    url = f"sqlite:///{database_path}"
    with TestClient(create_app(url, f"ws://127.0.0.1:{fake_downloader.port}")) as test_client:
        wait_for_link(test_client, 200)
        yield test_client
