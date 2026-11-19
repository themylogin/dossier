import asyncio
from datetime import UTC, datetime

from app.chats import Chat, DownloadState
from app.progress import ProgressHub

STEPS = 10


class StubDownloader:
    def __init__(self, chats: dict[int, Chat], hub: ProgressHub, step_seconds: float) -> None:
        self.chats = chats
        self.hub = hub
        self.step_seconds = step_seconds
        self.tasks: dict[int, asyncio.Task[None]] = {}

    def start(self, chat_id: int) -> None:
        running = self.tasks.get(chat_id)
        if running is not None:
            running.cancel()
        chat = self.chats[chat_id]
        chat.state = DownloadState()
        self.tasks[chat_id] = asyncio.create_task(self.simulate(chat))

    async def simulate(self, chat: Chat) -> None:
        start = datetime.now(UTC).replace(microsecond=0)
        history = start - chat.first_message_date
        for step in range(1, STEPS + 1):
            await asyncio.sleep(self.step_seconds)
            newest = chat.first_message_date + history * step / STEPS
            chat.state = DownloadState(
                messages_count=100 * step,
                oldest_message_date=chat.first_message_date,
                newest_message_date=newest.replace(microsecond=0),
                complete=step == STEPS,
            )
            await self.hub.publish(chat.id, chat.state)

    async def close(self) -> None:
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
