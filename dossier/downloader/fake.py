import asyncio
from datetime import UTC, datetime

from sqlalchemy import Engine, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from dossier.downloader.api import DownloaderApi, download_state
from dossier.models import Chat

STEPS = 10


class FakeDownloader:
    def __init__(self, engine: Engine, api: DownloaderApi, step_seconds: float) -> None:
        self.engine = engine
        self.api = api
        self.step_seconds = step_seconds
        self.chats = {
            1001: ("Alice Smith", "user", datetime(2023, 3, 14, 9, 26, 53, tzinfo=UTC)),
            1002: ("Bob Jones", "user", datetime(2024, 7, 1, 18, 4, 11, tzinfo=UTC)),
            -2001: ("Family", "group", datetime(2021, 11, 5, 7, 45, tzinfo=UTC)),
            -2002: ("Book Club", "group", datetime(2025, 2, 10, 12, 30, tzinfo=UTC)),
        }
        self.tasks: dict[int, asyncio.Task[None]] = {}

    def store_chats(self) -> None:
        with Session(self.engine) as session, session.begin():
            for chat_id, (name, chat_type, first_message_date) in self.chats.items():
                statement = insert(Chat).values(
                    chat_id=chat_id, name=name, type=chat_type, tracked=True, download_media=False
                )
                session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[Chat.chat_id], set_={"name": name, "type": chat_type}
                    )
                )

    def start(self, chat_id: int) -> None:
        if chat_id not in self.chats:
            return
        running = self.tasks.get(chat_id)
        if running is not None:
            running.cancel()
        self.tasks[chat_id] = asyncio.create_task(self.simulate(chat_id))

    async def simulate(self, chat_id: int) -> None:
        await self.api.publish(chat_id, download_state(0, None, None, 0, 0, False))
        with Session(self.engine) as session:
            media = bool(session.scalar(select(Chat.download_media).where(Chat.chat_id == chat_id)))
        files = 0
        pending = 0
        first_message_date = self.chats[chat_id][2]
        start = datetime.now(UTC).replace(microsecond=0)
        history = start - first_message_date
        for step in range(1, STEPS + 1):
            await asyncio.sleep(self.step_seconds)
            newest = first_message_date + history * step / STEPS
            if media:
                files = 10 * step
                pending = 10 * STEPS - files
            await self.api.publish(
                chat_id,
                download_state(
                    100 * step,
                    first_message_date.isoformat(),
                    newest.replace(microsecond=0).isoformat(),
                    files,
                    pending,
                    step == STEPS,
                ),
            )

    async def close(self) -> None:
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
