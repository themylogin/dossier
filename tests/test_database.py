from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
import pytest
from sqlalchemy import event, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dossier.database import create_database_engine
from dossier.models import Base, Chat, Message, MessageVersion
from tests.migrate import migrate


def test_empty_data_folder_gets_the_newest_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "messages.db"
    database_url = f"sqlite:///{database_path}"

    migrate(database_url)

    engine = create_database_engine(database_url)

    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
        version = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
    assert database_path.exists()
    assert tables == {"alembic_version", "chats", "message_versions", "messages", "users"}
    assert version == "0004"


def test_models_match_the_migrations(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)

    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert differences == []


def test_connections_use_wal_and_wait_for_locks(tmp_path: Path) -> None:
    engine = create_database_engine(f"sqlite:///{tmp_path / 'messages.db'}")

    with engine.connect() as connection:
        journal_mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar_one()
        synchronous = connection.exec_driver_sql("PRAGMA synchronous").scalar_one()
        busy_timeout = connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one()

    assert journal_mode == "wal"
    assert synchronous == 1
    assert busy_timeout == 5000


def test_write_transaction_starts_with_begin_immediate(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)
    engine.dispose()
    statements: list[str] = []
    event.listen(
        engine, "connect", lambda dbapi_connection, record: dbapi_connection.set_trace_callback(statements.append)
    )

    with Session(engine) as session, session.begin():
        session.add(Chat(chat_id=1, name="Alice", type="user", tracked=True, download_media=False))

    assert statements.index("BEGIN IMMEDIATE") < statements.index("COMMIT")


def test_message_without_a_date_is_rejected(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)

    with pytest.raises(IntegrityError, match="NOT NULL constraint failed: messages.date"):
        with Session(engine) as session, session.begin():
            session.add(Message(chat_id=-2001, message_id=1, text="hello", has_media=False))


def test_downgrade_and_upgrade_keep_the_messages(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)
    with Session(engine) as session, session.begin():
        session.add(Message(chat_id=-2001, message_id=1, date="2024-01-01T00:00:00+00:00", text="hi", has_media=False))
    engine.dispose()
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.downgrade(config, "0003")
    command.upgrade(config, "head")

    with Session(engine) as session:
        assert session.get_one(Message, 1).text == "hi"


def test_version_without_a_version_date_is_rejected(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'messages.db'}"
    migrate(database_url)
    engine = create_database_engine(database_url)

    with pytest.raises(IntegrityError, match="NOT NULL constraint failed: message_versions.version_date"):
        with Session(engine) as session, session.begin():
            session.add(MessageVersion(chat_id=-2001, message_id=1, text="hello", has_media=False))
