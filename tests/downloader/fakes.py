import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from telethon.tl.types import MessageMediaPhoto, User

from dossier.downloader.api import DownloaderApi, DownloadStateJson


class FakeClient:
    def __init__(
        self,
        dialogs: Iterable[SimpleNamespace] = (),
        histories: dict[int, list[SimpleNamespace]] | None = None,
        delay: float = 0,
        authorized: bool = True,
        before_message: Callable[[SimpleNamespace], None] | None = None,
        on_connect: Callable[[], Awaitable[None]] | None = None,
        while_running: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.dialogs = list(dialogs)
        self.histories = histories or {}
        self.delay = delay
        self.authorized = authorized
        self.before_message = before_message
        self.on_connect = on_connect
        self.while_running = while_running
        self.history_requests: list[tuple[int, int]] = []
        self.handlers: list[Callable[[SimpleNamespace], Awaitable[None]]] = []
        self.calls: list[str] = []

    async def connect(self) -> None:
        self.calls.append("connect")
        if self.on_connect is not None:
            await self.on_connect()

    async def is_user_authorized(self) -> bool:
        return self.authorized

    async def run_until_disconnected(self) -> None:
        self.calls.append("run_until_disconnected")
        if self.while_running is not None:
            await self.while_running()

    async def disconnect(self) -> None:
        self.calls.append("disconnect")

    def add_event_handler(self, callback: Callable[[SimpleNamespace], Awaitable[None]], event: object) -> None:
        self.handlers.append(callback)

    async def get_dialogs(self) -> list[SimpleNamespace]:
        return self.dialogs

    def iter_messages(self, chat_id: int, min_id: int, reverse: bool) -> AsyncIterator[SimpleNamespace]:
        self.history_requests.append((chat_id, min_id))
        return self.iterate(chat_id, min_id)

    async def iterate(self, chat_id: int, min_id: int) -> AsyncIterator[SimpleNamespace]:
        for message in self.histories.get(chat_id, []):
            if message.id > min_id:
                await asyncio.sleep(self.delay)
                if self.before_message is not None:
                    self.before_message(message)
                yield message

    async def download_media(self, media: object, file: str) -> str:
        await asyncio.sleep(self.delay)
        await asyncio.to_thread(Path(file).write_bytes, b"media")
        return file


class RecordingApi(DownloaderApi):
    def __init__(self) -> None:
        super().__init__()
        self.published: list[tuple[int, DownloadStateJson]] = []

    async def publish(self, chat_id: int, state: DownloadStateJson) -> None:
        self.published.append((chat_id, state))

    def states_of(self, chat_id: int) -> list[DownloadStateJson]:
        return [state for published_chat_id, state in self.published if published_chat_id == chat_id]


def make_dialog(chat_id: int, name: str, kind: str, top_message: int) -> SimpleNamespace:
    entity = SimpleNamespace(username=None)
    if kind == "user":
        entity = User(id=chat_id, first_name=name, username=None, bot=False)
    return SimpleNamespace(
        id=chat_id,
        name=name,
        is_user=kind == "user",
        is_group=kind == "group",
        is_channel=kind == "channel",
        entity=entity,
        dialog=SimpleNamespace(top_message=top_message),
    )


async def no_sender() -> None:
    return None


def make_message(
    chat_id: int, message_id: int, media: MessageMediaPhoto | None = None, date: datetime | None = None
) -> SimpleNamespace:
    if date is None:
        date = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=message_id)
    return SimpleNamespace(
        chat_id=chat_id,
        id=message_id,
        date=date,
        text=f"message {message_id}",
        sender_id=None,
        sender=None,
        grouped_id=None,
        media=media,
        get_sender=no_sender,
    )


def make_history(chat_id: int, count: int) -> list[SimpleNamespace]:
    return [make_message(chat_id, message_id) for message_id in range(1, count + 1)]
