import multiprocessing
from multiprocessing.queues import Queue
from pathlib import Path
import time

from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from dossier.database import create_database_engine
from dossier.downloader.downloader import Downloader
from dossier.models import Chat, Message
from tests.downloader.fakes import FakeClient, RecordingApi, make_dialog, make_history, start
from tests.migrate import migrate


def update_settings_like_the_backend(database_path: str, seconds: float, results: Queue[tuple[int, list[str]]]) -> None:
    engine = create_database_engine(f"sqlite:///{database_path}")
    updates = 0
    errors: list[str] = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with engine.begin() as connection:
                connection.execute(text("UPDATE chats SET download_media = NOT download_media WHERE chat_id = -2001"))
            updates += 1
        except OperationalError as error:
            errors.append(str(error))
        time.sleep(0.01)
    results.put((updates, errors))


async def test_downloader_and_backend_write_without_lock_errors(tmp_path: Path) -> None:
    database_path = tmp_path / "messages.db"
    database_url = f"sqlite:///{database_path}"
    migrate(database_url)
    engine = create_database_engine(database_url)
    with Session(engine) as session, session.begin():
        session.add(Chat(chat_id=-2001, name="Family", type="group", tracked=True, download_media=False))
    client = FakeClient(
        dialogs=[make_dialog(-2001, "Family", "group", 3000)], histories={-2001: make_history(-2001, 3000)}, delay=0.001
    )
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    writer = context.Process(target=update_settings_like_the_backend, args=(str(database_path), 3, results))
    writer.start()

    await start(Downloader(client, engine, tmp_path / "downloads", RecordingApi()))
    updates, errors = results.get(timeout=60)
    writer.join()

    with Session(engine) as session:
        stored = session.scalar(select(func.count()).select_from(Message))
    assert errors == []
    assert updates > 50
    assert stored == 3000
