import asyncio
from collections.abc import Callable
import logging
import os
from pathlib import Path
import sys

from telethon import TelegramClient, utils

from dossier.database import create_database_engine
from dossier.downloader.api import DownloaderApi
from dossier.downloader.config import ConfigError, load_telegram_settings
from dossier.downloader.downloader import Downloader
from dossier.downloader.fake import FakeDownloader

logger = logging.getLogger("downloader")


async def run(make_client: Callable[[], TelegramClient], database_path: Path, downloads_dir: Path, port: int) -> int:
    engine = create_database_engine(f"sqlite:///{database_path}")
    client = make_client()
    api = DownloaderApi()
    downloader = Downloader(client, engine, downloads_dir, api)
    api.states.update(downloader.initial_states())
    async with api.serve("0.0.0.0", port, downloader.clear_media_cache, lambda chat_id: downloader.clear_media_cache()):
        logger.info(f"Downloader API listening on port {port}")
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("The Telegram session is not logged in. Run: docker compose run --rm downloader login")
            await client.disconnect()
            return 1
        logger.info("Downloader started successfully!")
        await downloader.start_up()
        downloader.listen()
        await client.run_until_disconnected()
    return 0


async def fake(database_path: Path, port: int, step_seconds: float) -> int:
    engine = create_database_engine(f"sqlite:///{database_path}")
    api = DownloaderApi()
    fake_downloader = FakeDownloader(engine, api, step_seconds)
    fake_downloader.store_chats()
    async with api.serve("0.0.0.0", port, lambda: None, fake_downloader.start):
        logger.info(f"Fake downloader API listening on port {port}")
        for chat_id in fake_downloader.chats:
            fake_downloader.start(chat_id)
        try:
            await asyncio.Event().wait()
        finally:
            await fake_downloader.close()
    return 0


async def login(make_client: Callable[[], TelegramClient], phone: str) -> int:
    client = make_client()
    await client.start(phone=phone)
    me = await client.get_me()
    print(f"Logged in as {utils.get_display_name(me)}. The session is in the data folder.")
    await client.disconnect()
    return 0


def main(arguments: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    command = "run"
    if arguments:
        command = arguments[0]
    if command == "fake":
        return asyncio.run(fake(Path("/data/messages.db"), 8090, 0.5))
    if command not in ("run", "login"):
        logger.error(f"Unknown command: {command}. Use run, login, or fake.")
        return 2
    try:
        settings = load_telegram_settings(os.environ)
    except ConfigError as error:
        logger.error(str(error))
        return 1

    def make_client() -> TelegramClient:
        return TelegramClient("/data/dossier_bot", settings.api_id, settings.api_hash, flood_sleep_threshold=3600)

    if command == "login":
        return asyncio.run(login(make_client, settings.phone))
    return asyncio.run(run(make_client, Path("/data/messages.db"), Path("/downloads"), 8090))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
