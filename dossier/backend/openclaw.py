from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path, PurePosixPath
import sqlite3
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid

from sqlalchemy import create_engine

from dossier.models import Base


class OpenClawError(Exception):
    pass


@dataclass(frozen=True)
class OpenClawSettings:
    url: str
    token: str
    agent_id: str
    export_path: PurePosixPath


def load_openclaw_settings(environ: Mapping[str, str]) -> OpenClawSettings | None:
    url = environ.get("OPENCLAW_URL", "")
    token = environ.get("OPENCLAW_HOOK_TOKEN", "")
    export_path = environ.get("OPENCLAW_EXPORT_PATH", "")
    if not (url and token and export_path):
        return None
    return OpenClawSettings(url, token, environ.get("OPENCLAW_AGENT_ID", ""), PurePosixPath(export_path))


def export_chat(database_path: Path, exports_dir: Path, chat_id: int, now: datetime) -> Path:
    path = exports_dir / f"{chat_id}-{now.astimezone(UTC):%Y-%m-%d_%H-%M-%S}.sqlite"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    conditions = {
        "chats": "chat_id = :chat_id",
        "messages": "chat_id = :chat_id",
        "message_versions": "chat_id = :chat_id",
        "users": "user_id IN (SELECT sender_id FROM main.messages) OR user_id = :chat_id",
    }
    # The source is attached read-only, so the copy holds no write lock that the downloader needs.
    connection = sqlite3.connect(path.as_uri(), uri=True)
    try:
        connection.execute("ATTACH DATABASE ? AS source", (f"{database_path.as_uri()}?mode=ro",))
        with connection:
            for table, condition in conditions.items():
                columns = ", ".join(Base.metadata.tables[table].columns.keys())
                connection.execute(
                    f"INSERT INTO main.{table} ({columns}) SELECT {columns} FROM source.{table} WHERE {condition}",
                    {"chat_id": chat_id},
                )
    finally:
        connection.close()
    return path


def submit(settings: OpenClawSettings, text: str, chat_name: str, chat_id: int, file_path: PurePosixPath) -> str:
    message = (
        f'{text}\n\nThe Telegram chat "{chat_name}" (id {chat_id}) is in the SQLite database {file_path}. '
        "Its tables are chats, messages, message_versions (earlier versions of edited messages), and users."
    )
    body = {"message": message, "name": "Dossier"}
    if settings.agent_id:
        body["agentId"] = settings.agent_id
    request = Request(
        f"{settings.url}/hooks/agent",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {settings.token}",
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            answer = json.load(response)
    except HTTPError as error:
        raise OpenClawError(f"OpenClaw rejected the request: HTTP {error.code}") from error
    except OSError as error:
        raise OpenClawError(f"OpenClaw is unreachable: {error}") from error
    return str(answer["runId"])
