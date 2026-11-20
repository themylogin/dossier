import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto, Photo, User

from dossier.downloader.api import DownloaderApi, DownloadStateJson
from dossier.downloader.downloader import Downloader
from dossier.models import Chat, Message


class FakeClient:
    def __init__(
        self,
        dialogs: Iterable[SimpleNamespace] = (),
        histories: dict[int, list[SimpleNamespace]] | None = None,
        delay: float = 0,
        authorized: bool = True,
        before_message: Callable[[SimpleNamespace], None] | None = None,
        before_download: Callable[[SimpleNamespace], None] | None = None,
        after_history: Callable[[int], Awaitable[None]] | None = None,
        on_connect: Callable[[], Awaitable[None]] | None = None,
        while_running: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.dialogs = list(dialogs)
        self.histories = histories or {}
        self.delay = delay
        self.authorized = authorized
        self.before_message = before_message
        self.before_download = before_download
        self.after_history = after_history
        self.on_connect = on_connect
        self.while_running = while_running
        self.history_requests: list[tuple[int, str, int]] = []
        self.message_requests: list[list[int]] = []
        self.downloaded: list[int] = []
        self.handlers: list[tuple[object, Callable[[SimpleNamespace], Awaitable[None]]]] = []
        self.dialog_reads = 0
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
        self.handlers.append((event, callback))

    def handler(self, event_type: type[object]) -> Callable[[SimpleNamespace], Awaitable[None]]:
        return next(callback for event, callback in self.handlers if isinstance(event, event_type))

    async def get_dialogs(self) -> list[SimpleNamespace]:
        self.dialog_reads += 1
        return list(self.dialogs)

    def iter_messages(
        self, chat_id: int, min_id: int = 0, offset_id: int = 0, reverse: bool = False
    ) -> AsyncIterator[SimpleNamespace]:
        history = self.histories.get(chat_id, [])
        if reverse:
            self.history_requests.append((chat_id, "after", min_id))
            return self.iterate(chat_id, [message for message in history if message.id > min_id])
        self.history_requests.append((chat_id, "before", offset_id))
        older = [message for message in history if offset_id == 0 or message.id < offset_id]
        return self.iterate(chat_id, sorted(older, key=lambda message: message.id, reverse=True))

    async def iterate(self, chat_id: int, messages: list[SimpleNamespace]) -> AsyncIterator[SimpleNamespace]:
        for message in messages:
            await asyncio.sleep(self.delay)
            if self.before_message is not None:
                self.before_message(message)
            yield message
        if self.after_history is not None:
            await self.after_history(chat_id)

    async def get_messages(self, chat_id: int, ids: list[int]) -> list[SimpleNamespace | None]:
        self.message_requests.append(ids)
        by_id = {message.id: message for message in self.histories.get(chat_id, [])}
        return [by_id.get(message_id) for message_id in ids]

    async def download_media(self, message: SimpleNamespace, file: str) -> str | None:
        await asyncio.sleep(self.delay)
        if self.before_download is not None:
            self.before_download(message)
        if not isinstance(message.media, MessageMediaPhoto | MessageMediaDocument):
            return None
        self.downloaded.append(message.id)
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


async def download_queued(downloader: Downloader) -> None:
    async with asyncio.TaskGroup() as tasks:
        workers = [
            tasks.create_task(downloader.download_queued_chats(downloader.history_queue)),
            tasks.create_task(downloader.download_queued_chats(downloader.live_queue)),
            tasks.create_task(downloader.download_queued_media()),
        ]
        await downloader.history_queue.join()
        await downloader.live_queue.join()
        await downloader.media_queue.join()
        for worker in workers:
            worker.cancel()


async def start(downloader: Downloader) -> None:
    downloader.listen()
    await downloader.start_up()
    await download_queued(downloader)


def stored_message_ids(engine: Engine, chat_id: int) -> Sequence[int]:
    with Session(engine) as session:
        return session.scalars(
            select(Message.message_id).where(Message.chat_id == chat_id).order_by(Message.message_id)
        ).all()


def store_chat(engine: Engine, chat_id: int, message_ids: Iterable[int], downloaded: bool) -> None:
    with Session(engine) as session, session.begin():
        session.merge(
            Chat(
                chat_id=chat_id,
                name="Chat",
                type="group",
                download_media=False,
                downloaded=downloaded,
            )
        )
        for message_id in message_ids:
            message = make_message(chat_id, message_id)
            session.add(
                Message(
                    chat_id=chat_id,
                    message_id=message_id,
                    date=message.date.isoformat(),
                    text=message.text,
                    has_media=False,
                )
            )


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


def make_photo(media_id: int) -> MessageMediaPhoto:
    return MessageMediaPhoto(photo=Photo(id=media_id, access_hash=0, file_reference=b"", date=None, sizes=[], dc_id=2))


def make_message(
    chat_id: int,
    message_id: int,
    media: object | None = None,
    date: datetime | None = None,
    text: str | None = None,
    edit_date: datetime | None = None,
) -> SimpleNamespace:
    if date is None:
        date = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=message_id)
    return SimpleNamespace(
        chat_id=chat_id,
        id=message_id,
        date=date,
        text=text or f"message {message_id}",
        sender_id=None,
        sender=None,
        grouped_id=None,
        media=media,
        edit_date=edit_date,
        get_sender=no_sender,
    )


def make_history(chat_id: int, count: int) -> list[SimpleNamespace]:
    return [make_message(chat_id, message_id) for message_id in range(1, count + 1)]
