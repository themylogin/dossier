from pathlib import Path
import sqlite3

from sqlalchemy import select
from sqlalchemy.orm import Session

from dossier.database import create_database_engine
from dossier.models import Chat, Message
from tests.migrate import migrate


def create_bot_py_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            date TEXT,
            text TEXT,
            sender_id INTEGER,
            grouped_id INTEGER,
            has_media BOOLEAN,
            media_type TEXT,
            media_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, message_id)
        )
    """)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_chat_message ON messages(chat_id, message_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_date ON messages(date)")
    connection.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT,
            username TEXT,
            tracked BOOLEAN,
            downloads_media BOOLEAN,
            first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            is_bot BOOLEAN,
            first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.execute(
        "INSERT INTO chats (chat_id, name, type, tracked, downloads_media) VALUES (-2001, 'Family', 'group', 1, 1)"
    )
    for message_id in (1, 2, 3):
        connection.execute(
            "INSERT INTO messages (chat_id, message_id, date, text, has_media) VALUES (?, ?, ?, ?, 0)",
            (-2001, message_id, f"2024-01-0{message_id}T10:00:00+00:00", f"message {message_id}"),
        )
    connection.commit()
    connection.close()


def test_database_from_bot_py_is_adopted(tmp_path: Path) -> None:
    database_path = tmp_path / "messages.db"
    create_bot_py_database(database_path)
    database_url = f"sqlite:///{database_path}"

    migrate(database_url)

    engine = create_database_engine(database_url)

    with Session(engine) as session:
        version = session.connection().exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
        message_ids = session.scalars(select(Message.message_id).order_by(Message.message_id)).all()
        chat = session.get_one(Chat, -2001)
    assert version == "0002"
    assert message_ids == [1, 2, 3]
    assert chat.download_media
