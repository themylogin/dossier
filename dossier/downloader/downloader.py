import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
import logging
import os
from pathlib import Path

from sqlalchemy import Engine, func, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session
from telethon import TelegramClient, events, utils
from telethon.tl.custom import Dialog
from telethon.tl.custom import Message as TelegramMessage
from telethon.tl.types import (
    Document,
    DocumentAttributeFilename,
    MessageMediaDocument,
    MessageMediaPhoto,
    PeerChannel,
    Photo,
    UpdateChannel,
    User,
)

from dossier.downloader.api import DownloaderApi, DownloadStateJson, download_state
from dossier.models import Chat, Message, MessageVersion, file_pending
from dossier.models import User as UserRow

logger = logging.getLogger(__name__)


def media_id(message: TelegramMessage) -> int | None:
    media = message.media
    if isinstance(media, MessageMediaPhoto) and isinstance(media.photo, Photo):
        return int(media.photo.id)
    if isinstance(media, MessageMediaDocument) and isinstance(media.document, Document):
        return int(media.document.id)
    return None


class Downloader:
    def __init__(self, client: TelegramClient, engine: Engine, downloads_dir: Path, api: DownloaderApi) -> None:
        self.client = client
        self.engine = engine
        self.downloads_dir = downloads_dir
        self.api = api
        self.complete: set[int] = set()
        # The value marks that a message arrived, so the download runs one more newer pass.
        self.downloading: dict[int, bool] = {}
        self.failed: set[int] = set()
        self.outside: set[int] = set()
        self.names: dict[int, str] = {}
        self.history_queue: asyncio.Queue[int] = asyncio.Queue()
        self.live_queue: asyncio.Queue[int] = asyncio.Queue()
        self.media_queue: asyncio.Queue[int] = asyncio.Queue()
        self.media_pending: set[int] = set()
        self.sync_lock = asyncio.Lock()
        self.seen_sender_ids: set[int] = set()
        self.media_flags: dict[int, bool] | None = None

    def initial_states(self) -> dict[int, DownloadStateJson]:
        with Session(self.engine) as session:
            chat_ids = session.scalars(select(Chat.chat_id)).all()
            rows = session.execute(
                select(
                    Message.chat_id,
                    func.count(),
                    func.min(Message.date),
                    func.max(Message.date),
                    func.count(Message.media_path),
                    func.count().filter(file_pending()),
                ).group_by(Message.chat_id)
            ).all()
        states = {chat_id: download_state(0, None, None, 0, 0, False) for chat_id in chat_ids}
        for chat_id, count, oldest, newest, files, pending in rows:
            if chat_id in states:
                states[chat_id] = download_state(count, oldest, newest, files, pending, False)
        return states

    def state(self, chat_id: int) -> DownloadStateJson:
        with Session(self.engine) as session:
            count, oldest, newest, files, pending = session.execute(
                select(
                    func.count(),
                    func.min(Message.date),
                    func.max(Message.date),
                    func.count(Message.media_path),
                    func.count().filter(file_pending()),
                ).where(Message.chat_id == chat_id)
            ).one()
        return download_state(count, oldest, newest, files, pending, chat_id in self.complete)

    async def report(self, chat_id: int) -> None:
        await self.api.publish(chat_id, self.state(chat_id))

    def last_message_id(self, chat_id: int) -> int:
        with Session(self.engine) as session:
            return session.scalar(select(func.max(Message.message_id)).where(Message.chat_id == chat_id)) or 0

    def first_message_id(self, chat_id: int) -> int:
        with Session(self.engine) as session:
            return session.scalar(select(func.min(Message.message_id)).where(Message.chat_id == chat_id)) or 0

    def history_checked(self, chat_id: int) -> bool:
        with Session(self.engine) as session:
            return bool(session.scalar(select(Chat.history_checked).where(Chat.chat_id == chat_id)))

    def tracks(self, chat_id: int) -> bool:
        return chat_id in self.complete or chat_id in self.downloading or chat_id in self.failed

    async def start_up(self) -> None:
        with Session(self.engine) as session:
            self.seen_sender_ids.update(session.scalars(select(UserRow.user_id)))
        await self.check()

    async def check(self) -> None:
        async with self.sync_lock:
            await self.read_dialogs()
        self.clear_media_cache()
        with Session(self.engine) as session:
            chat_ids = session.scalars(select(Chat.chat_id).where(Chat.download_media)).all()
        for chat_id in chat_ids:
            self.queue_media(chat_id)

    async def check_forever(self) -> None:
        while True:
            await asyncio.sleep(900)
            await self.check()

    async def find_chat(self, chat_id: int) -> None:
        if self.tracks(chat_id) or chat_id in self.outside:
            return
        async with self.sync_lock:
            if self.tracks(chat_id) or chat_id in self.outside:
                return
            await self.read_dialogs()
            if not self.tracks(chat_id):
                self.outside.add(chat_id)
                logger.info(f"Chat {chat_id} is not in the dialog list, so its messages are dropped")

    async def read_dialogs(self) -> None:
        dialogs = await self.client.get_dialogs()
        new_dialogs = [dialog for dialog in dialogs if not self.tracks(dialog.id)]
        with Session(self.engine) as session, session.begin():
            for dialog in new_dialogs:
                self.save_dialog(session, dialog)
        logger.info(f"Read {len(dialogs)} dialogs, {len(new_dialogs)} of them not tracked yet")
        with Session(self.engine) as session:
            newest_ids = dict(
                session.execute(select(Message.chat_id, func.max(Message.message_id)).group_by(Message.chat_id)).all()
            )
            checked = set(session.scalars(select(Chat.chat_id).where(Chat.history_checked)))
        for dialog in dialogs:
            chat_id = dialog.id
            self.names[chat_id] = dialog.name
            if chat_id in self.downloading:
                continue
            newer = dialog.dialog.top_message > newest_ids.get(chat_id, 0)
            if chat_id in self.complete:
                if newer:
                    self.complete.discard(chat_id)
                    self.queue_download(self.live_queue, chat_id, True)
                continue
            self.outside.discard(chat_id)
            self.failed.discard(chat_id)
            if chat_id not in checked:
                self.queue_download(self.history_queue, chat_id, newer)
            elif newer:
                self.queue_download(self.live_queue, chat_id, True)
            else:
                self.complete.add(chat_id)
                await self.report(chat_id)

    def queue_download(self, queue: asyncio.Queue[int], chat_id: int, newer: bool) -> None:
        self.downloading[chat_id] = newer
        queue.put_nowait(chat_id)
        logger.info(f"Queued chat '{self.names.get(chat_id, chat_id)}' ({chat_id})")

    def listen(self) -> None:
        self.client.add_event_handler(self.on_new_message, events.NewMessage())
        self.client.add_event_handler(self.on_message_edited, events.MessageEdited())
        self.client.add_event_handler(self.on_chat_action, events.ChatAction())
        self.client.add_event_handler(self.on_channel_update, events.Raw(UpdateChannel))
        logger.info("Listening for new messages, edits, chat actions, and channel updates in all chats...")

    async def on_chat_action(self, event: events.ChatAction.Event) -> None:
        await self.find_chat(event.chat_id)

    async def on_channel_update(self, update: UpdateChannel) -> None:
        chat_id = utils.get_peer_id(PeerChannel(update.channel_id))
        if not self.tracks(chat_id):
            self.outside.discard(chat_id)
        await self.find_chat(chat_id)

    async def on_new_message(self, event: events.NewMessage.Event) -> None:
        chat_id = event.chat_id
        logger.info(f"New message in chat {chat_id}: {event.message.id}")
        await self.find_chat(chat_id)
        if chat_id in self.downloading:
            self.downloading[chat_id] = True
        elif chat_id in self.complete:
            self.complete.discard(chat_id)
            self.queue_download(self.live_queue, chat_id, True)

    async def on_message_edited(self, event: events.MessageEdited.Event) -> None:
        if self.tracks(event.chat_id):
            self.store_version(event.message)

    async def download_queued_chats(self, queue: asyncio.Queue[int]) -> None:
        while True:
            chat_id = await queue.get()
            try:
                await self.download_history(chat_id)
            except Exception:
                logger.exception(f"Error downloading chat '{self.names.get(chat_id, chat_id)}' ({chat_id})")
                del self.downloading[chat_id]
                self.failed.add(chat_id)
                await self.report(chat_id)
            queue.task_done()

    async def download_history(self, chat_id: int) -> None:
        name = self.names.get(chat_id, str(chat_id))
        logger.info(f"Starting download for '{name}' ({chat_id})")
        count = 0
        while True:
            while self.downloading[chat_id]:
                self.downloading[chat_id] = False
                newer = self.client.iter_messages(chat_id, min_id=self.last_message_id(chat_id), reverse=True)
                count = await self.store_history(chat_id, newer, count)
            if not self.history_checked(chat_id):
                older = self.client.iter_messages(chat_id, offset_id=self.first_message_id(chat_id))
                count = await self.store_history(chat_id, older, count)
                if utils.resolve_id(chat_id)[1] is PeerChannel:
                    count = await self.fill_gaps(chat_id, count)
                with Session(self.engine) as session, session.begin():
                    session.execute(update(Chat).where(Chat.chat_id == chat_id).values(history_checked=True))
            # No await may come between this check and the move to complete. Otherwise a new
            # message can arrive after the check and get neither stored nor fetched.
            if not self.downloading[chat_id]:
                break
        del self.downloading[chat_id]
        self.complete.add(chat_id)
        await self.report(chat_id)
        self.queue_media(chat_id)
        logger.info(f"Completed download for '{name}' ({chat_id}). Messages stored: {count}")

    async def store_history(self, chat_id: int, messages: AsyncIterator[TelegramMessage], count: int) -> int:
        async for message in messages:
            await self.store_message(message)
            count += 1
            if count % 100 == 0:
                await self.report(chat_id)
                logger.info(f"Downloaded {count} messages from '{self.names.get(chat_id, chat_id)}' so far...")
        return count

    async def fill_gaps(self, chat_id: int, count: int) -> int:
        with Session(self.engine) as session:
            stored_ids = session.scalars(
                select(Message.message_id).where(Message.chat_id == chat_id).order_by(Message.message_id)
            ).all()
        missing = [
            message_id
            for previous, following in zip(stored_ids, stored_ids[1:])
            for message_id in range(previous + 1, following)
        ]
        logger.info(f"Requesting {len(missing)} missing messages of chat {chat_id}")
        for start in range(0, len(missing), 100):
            for message in await self.client.get_messages(chat_id, ids=missing[start : start + 100]):
                if message is not None:
                    await self.store_message(message)
                    count += 1
        return count

    def clear_media_cache(self) -> None:
        self.media_flags = None

    def settings_changed(self, chat_id: int) -> None:
        self.clear_media_cache()
        self.queue_media(chat_id)

    def media_enabled(self, chat_id: int) -> bool:
        if self.media_flags is None:
            with Session(self.engine) as session:
                self.media_flags = dict(session.execute(select(Chat.chat_id, Chat.download_media)).all())
        return self.media_flags.get(chat_id, False)

    def queue_media(self, chat_id: int) -> None:
        if chat_id in self.media_pending or not self.media_enabled(chat_id):
            return
        self.media_pending.add(chat_id)
        self.media_queue.put_nowait(chat_id)

    async def download_queued_media(self) -> None:
        while True:
            chat_id = await self.media_queue.get()
            self.media_pending.discard(chat_id)
            try:
                await self.download_chat_media(chat_id)
            except Exception:
                logger.exception(f"Error downloading the media of chat {chat_id}")
            self.media_queue.task_done()

    async def download_chat_media(self, chat_id: int) -> None:
        saved = 0
        before = None
        while True:
            statement = (
                select(Message.message_id)
                .where(Message.chat_id == chat_id, file_pending())
                .order_by(Message.message_id.desc())
                .limit(100)
            )
            if before is not None:
                statement = statement.where(Message.message_id < before)
            with Session(self.engine) as session:
                message_ids = session.scalars(statement).all()
            if not message_ids:
                break
            before = message_ids[-1]
            messages = await self.client.get_messages(chat_id, ids=list(message_ids))
            for message_id, message in zip(message_ids, messages):
                # The file in progress completes. The setting stops the run before the next file.
                if not self.media_enabled(chat_id):
                    await self.report(chat_id)
                    return
                if message is None:
                    self.save_file(chat_id, message_id, "other", None)
                    continue
                self.store_version(message)
                if message.media is None:
                    continue
                try:
                    file = await self.download_media(message, self.media_folder(chat_id, message_id))
                except Exception as error:
                    logger.error(f"Error downloading media from message {message_id} of chat {chat_id}: {error}")
                    continue
                if file is None:
                    self.save_file(chat_id, message_id, "other", None)
                    continue
                self.save_file(chat_id, message_id, *file)
                saved += 1
                if saved % 10 == 0:
                    await self.report(chat_id)
        await self.report(chat_id)

    def save_file(self, chat_id: int, message_id: int, media_type: str, media_path: str | None) -> None:
        with Session(self.engine) as session, session.begin():
            session.execute(
                update(Message)
                .where(Message.chat_id == chat_id, Message.message_id == message_id)
                .values(media_type=media_type, media_path=media_path)
            )

    def media_folder(self, chat_id: int, message_id: int) -> Path:
        padded = str(message_id).zfill(6)
        folder = self.downloads_dir / str(chat_id)
        for start in range(0, 6, 2):
            folder = folder / padded[start : start + 2]
        folder = folder / str(message_id)
        with Session(self.engine) as session:
            replaced_at = session.scalar(
                select(Message.media_replaced_at).where(Message.chat_id == chat_id, Message.message_id == message_id)
            )
        if replaced_at is not None:
            folder = folder / datetime.fromisoformat(replaced_at).astimezone(UTC).strftime("%Y-%m-%d_%H-%M-%S")
        return folder

    async def download_media(self, message: TelegramMessage, folder: Path) -> tuple[str, str] | None:
        media = message.media
        if isinstance(media, MessageMediaPhoto) and isinstance(media.photo, Photo):
            media_type = "photo"
            filename = f"photo_{message.id}.jpg"
        elif isinstance(media, MessageMediaDocument) and isinstance(media.document, Document):
            mime_type = media.document.mime_type or ""
            if "video" in mime_type:
                media_type = "video"
                extension = ".mp4"
            elif "image" in mime_type:
                media_type = "image"
                extension = ".jpg"
            else:
                media_type = "document"
                extension = ""
            filename = f"document_{message.id}{extension}"
            for attribute in media.document.attributes:
                if isinstance(attribute, DocumentAttributeFilename):
                    name = Path(attribute.file_name).name
                    if name not in ("", ".."):
                        filename = name
                    break
        else:
            return None

        await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True)
        file_path = folder / filename
        logger.info(f"Downloading {media_type} from message {message.id}: {filename}")
        # Telethon refetches an expired file reference only when it gets the message.
        if await self.client.download_media(message, file=str(file_path)) is None:
            return None
        date = message.date
        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)
        os.utime(file_path, (date.timestamp(), date.timestamp()))
        logger.info(f"Media saved: {file_path}")
        return media_type, str(file_path)

    def store_version(self, message: TelegramMessage) -> None:
        if message.edit_date is None:
            return
        edit_date = message.edit_date.isoformat()
        with Session(self.engine) as session, session.begin():
            row = session.scalars(
                select(Message).where(Message.chat_id == message.chat_id, Message.message_id == message.id)
            ).one_or_none()
            if row is None or (row.edit_date is not None and edit_date <= row.edit_date):
                return
            new_media_id = media_id(message)
            # A row from before the upgrade has media but no media id. Its media counts as unchanged.
            media_unknown = row.media_id is None and row.has_media
            replaced = message.media is not None and new_media_id != row.media_id and not media_unknown
            text = message.text or ""
            if replaced or text != row.text:
                session.execute(
                    insert(MessageVersion)
                    .values(
                        chat_id=row.chat_id,
                        message_id=row.message_id,
                        version_date=row.edit_date or row.date,
                        text=row.text,
                        has_media=row.has_media,
                        media_type=row.media_type,
                        media_path=row.media_path,
                        media_id=row.media_id,
                    )
                    .on_conflict_do_nothing()
                )
            row.text = text
            row.edit_date = edit_date
            row.has_media = message.media is not None
            row.media_id = new_media_id
            if replaced:
                row.media_type = None
                row.media_path = None
                row.media_replaced_at = edit_date
        if replaced:
            logger.info(f"Message {message.id} of chat {message.chat_id} got new media")
            self.queue_media(message.chat_id)

    async def store_message(self, message: TelegramMessage) -> None:
        sender = await self.fetch_new_sender(message)
        with Session(self.engine) as session, session.begin():
            if sender is not None:
                self.save_user(session, sender)
            self.save_message(session, message)

    async def fetch_new_sender(self, message: TelegramMessage) -> User | None:
        sender_id = message.sender_id
        if sender_id is None or sender_id in self.seen_sender_ids:
            return None
        self.seen_sender_ids.add(sender_id)
        sender = message.sender
        if sender is None:
            try:
                sender = await message.get_sender()
            except Exception as error:
                logger.warning(f"Cannot resolve sender {sender_id}: {error}")
                return None
        if isinstance(sender, User):
            return sender
        return None

    def save_dialog(self, session: Session, dialog: Dialog) -> None:
        if dialog.is_user:
            chat_type = "user"
        elif dialog.is_group:
            chat_type = "group"
        else:
            chat_type = "channel"
        self.save_chat(session, dialog.id, dialog.name, chat_type, getattr(dialog.entity, "username", None))
        if isinstance(dialog.entity, User):
            self.save_user(session, dialog.entity)

    def save_chat(self, session: Session, chat_id: int, name: str, chat_type: str, username: str | None) -> None:
        statement = insert(Chat).values(
            chat_id=chat_id,
            name=name,
            type=chat_type,
            username=username,
            tracked=True,
            download_media=False,
            history_checked=False,
        )
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[Chat.chat_id],
                set_={
                    "name": statement.excluded.name,
                    "type": statement.excluded.type,
                    "username": statement.excluded.username,
                    "tracked": True,
                    "updated_at": func.current_timestamp(),
                },
            )
        )

    def save_user(self, session: Session, user: User) -> None:
        statement = insert(UserRow).values(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            is_bot=user.bot,
        )
        kept = {
            column: func.coalesce(statement.excluded[column], getattr(UserRow, column))
            for column in ("username", "first_name", "last_name", "phone", "is_bot")
        }
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[UserRow.user_id], set_={**kept, "updated_at": func.current_timestamp()}
            )
        )
        self.seen_sender_ids.add(user.id)

    def save_message(self, session: Session, message: TelegramMessage) -> None:
        edit_date = None
        if message.edit_date is not None:
            edit_date = message.edit_date.isoformat()
        session.execute(
            insert(Message)
            .values(
                chat_id=message.chat_id,
                message_id=message.id,
                date=message.date.isoformat(),
                text=message.text or "",
                sender_id=message.sender_id,
                grouped_id=getattr(message, "grouped_id", None),
                has_media=message.media is not None,
                edit_date=edit_date,
                media_id=media_id(message),
            )
            .on_conflict_do_nothing()
        )
