from datetime import UTC
import logging
import os
from pathlib import Path

from sqlalchemy import Engine, func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session
from telethon import TelegramClient, events, utils
from telethon.tl.custom import Dialog
from telethon.tl.custom import Message as TelegramMessage
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto, User

from dossier.downloader.api import DownloaderApi, DownloadStateJson, download_state
from dossier.models import Chat, Message
from dossier.models import User as UserRow

logger = logging.getLogger(__name__)


class Downloader:
    def __init__(self, client: TelegramClient, engine: Engine, downloads_dir: Path, api: DownloaderApi) -> None:
        self.client = client
        self.engine = engine
        self.downloads_dir = downloads_dir
        self.api = api
        self.complete: set[int] = set()
        self.seen_sender_ids: set[int] = set()
        self.known_chat_ids: set[int] = set()
        self.media_flags: dict[int, bool] | None = None

    def initial_states(self) -> dict[int, DownloadStateJson]:
        with Session(self.engine) as session:
            chat_ids = session.scalars(select(Chat.chat_id)).all()
            rows = session.execute(
                select(Message.chat_id, func.count(), func.min(Message.date), func.max(Message.date)).group_by(
                    Message.chat_id
                )
            ).all()
        totals = {chat_id: (count, oldest, newest) for chat_id, count, oldest, newest in rows}
        states = {}
        for chat_id in chat_ids:
            count, oldest, newest = totals.get(chat_id, (0, None, None))
            states[chat_id] = download_state(count, oldest, newest, False)
        return states

    def state(self, chat_id: int) -> DownloadStateJson:
        with Session(self.engine) as session:
            count, oldest, newest = session.execute(
                select(func.count(), func.min(Message.date), func.max(Message.date)).where(Message.chat_id == chat_id)
            ).one()
        return download_state(count, oldest, newest, chat_id in self.complete)

    async def report(self, chat_id: int) -> None:
        await self.api.publish(chat_id, self.state(chat_id))

    def last_message_id(self, chat_id: int) -> int:
        with Session(self.engine) as session:
            return session.scalar(select(func.max(Message.message_id)).where(Message.chat_id == chat_id)) or 0

    async def start_up(self) -> None:
        with Session(self.engine) as session:
            self.seen_sender_ids.update(session.scalars(select(UserRow.user_id)))
        dialogs = await self.client.get_dialogs()
        with Session(self.engine) as session, session.begin():
            for dialog in dialogs:
                self.save_dialog(session, dialog)
        logger.info(f"Stored {len(dialogs)} dialogs")

        pending = []
        for dialog in dialogs:
            if dialog.dialog.top_message > self.last_message_id(dialog.id):
                pending.append(dialog)
            else:
                self.complete.add(dialog.id)
                await self.report(dialog.id)
        logger.info(f"{len(pending)} chats have new messages, {len(dialogs) - len(pending)} are up to date")

        for dialog in pending:
            try:
                await self.download_history(dialog.id, dialog.name)
            except Exception:
                logger.exception(f"Error downloading chat '{dialog.name}' ({dialog.id})")

    def listen(self) -> None:
        self.client.add_event_handler(self.on_new_message, events.NewMessage())
        logger.info("Listening for new messages in all chats...")

    async def on_new_message(self, event: events.NewMessage.Event) -> None:
        message = event.message
        logger.info(f"New message in chat {message.chat_id}: {message.id}")
        if event.chat_id not in self.known_chat_ids:
            await self.store_event_chat(event)
        await self.store_message(message)
        await self.report(message.chat_id)

    async def store_event_chat(self, event: events.NewMessage.Event) -> None:
        try:
            chat = await event.get_chat()
        except Exception as error:
            logger.error(f"Error resolving chat {event.chat_id}: {error}")
            return
        if event.is_private:
            chat_type = "user"
        elif event.is_group:
            chat_type = "group"
        else:
            chat_type = "channel"
        with Session(self.engine) as session, session.begin():
            self.save_chat(
                session, event.chat_id, utils.get_display_name(chat), chat_type, getattr(chat, "username", None)
            )
            if isinstance(chat, User):
                self.save_user(session, chat)
        self.complete.add(event.chat_id)

    async def download_history(self, chat_id: int, chat_name: str) -> None:
        last_message_id = self.last_message_id(chat_id)
        logger.info(f"Starting download for '{chat_name}' ({chat_id}), last message ID: {last_message_id}")
        count = 0
        async for message in self.client.iter_messages(chat_id, min_id=last_message_id, reverse=True):
            await self.store_message(message)
            count += 1
            if count % 100 == 0:
                await self.report(chat_id)
                logger.info(f"Downloaded {count} messages from '{chat_name}' so far...")
        self.complete.add(chat_id)
        await self.report(chat_id)
        logger.info(f"Completed download for '{chat_name}' ({chat_id}). Total messages: {count}")

    def clear_media_cache(self) -> None:
        self.media_flags = None

    def media_enabled(self, chat_id: int) -> bool:
        if self.media_flags is None:
            with Session(self.engine) as session:
                self.media_flags = dict(session.execute(select(Chat.chat_id, Chat.download_media)).all())
        return self.media_flags.get(chat_id, False)

    async def store_message(self, message: TelegramMessage) -> None:
        sender = await self.fetch_new_sender(message)
        media_type = None
        media_path = None
        if message.media and self.media_enabled(message.chat_id):
            media_type, media_path = await self.download_media(message)
        with Session(self.engine) as session, session.begin():
            if sender is not None:
                self.save_user(session, sender)
            self.save_message(session, message, media_type, media_path)

    async def download_media(self, message: TelegramMessage) -> tuple[str | None, str | None]:
        if isinstance(message.media, MessageMediaPhoto):
            media_type = "photo"
            filename = f"photo_{message.id}.jpg"
        elif isinstance(message.media, MessageMediaDocument):
            document = message.media.document
            if "video" in document.mime_type:
                media_type = "video"
                extension = ".mp4"
            elif "image" in document.mime_type:
                media_type = "image"
                extension = ".jpg"
            else:
                media_type = "document"
                extension = ""
            filename = f"document_{message.id}{extension}"
            for attribute in document.attributes:
                if hasattr(attribute, "file_name"):
                    filename = attribute.file_name
                    break
        else:
            return None, None

        date = message.date
        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)
        timestamp = date.timestamp()

        file_path = self.hierarchical_path(message.chat_id, message.id, filename)
        try:
            logger.info(f"Downloading {media_type} from message {message.id}: {filename}")
            await self.client.download_media(message.media, file=str(file_path))
            os.utime(file_path, (timestamp, timestamp))
        except Exception as error:
            logger.error(f"Error downloading media from message {message.id}: {error}")
            return media_type, None
        logger.info(f"Media saved: {file_path}")
        return media_type, str(file_path)

    def hierarchical_path(self, chat_id: int, message_id: int, filename: str) -> Path:
        padded = str(message_id).zfill(6)
        path = self.downloads_dir / str(chat_id)
        for start in range(0, 6, 2):
            path = path / padded[start : start + 2]
        path = path / str(message_id)
        path.mkdir(parents=True, exist_ok=True)
        return path / filename

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
            chat_id=chat_id, name=name, type=chat_type, username=username, tracked=True, download_media=False
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
        self.known_chat_ids.add(chat_id)

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

    def save_message(
        self, session: Session, message: TelegramMessage, media_type: str | None, media_path: str | None
    ) -> None:
        statement = insert(Message).values(
            chat_id=message.chat_id,
            message_id=message.id,
            date=message.date.isoformat(),
            text=message.text or "",
            sender_id=message.sender_id,
            grouped_id=getattr(message, "grouped_id", None),
            has_media=message.media is not None,
            media_type=media_type,
            media_path=media_path,
        )
        replaced = ("date", "text", "sender_id", "grouped_id", "has_media", "media_type", "media_path")
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[Message.chat_id, Message.message_id],
                set_={column: statement.excluded[column] for column in replaced},
            )
        )
