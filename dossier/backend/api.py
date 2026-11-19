from fastapi.concurrency import run_in_threadpool
from jsonrpcserver import Error, InvalidParams, Result, Success
from pydantic import ValidationError
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from dossier import models
from dossier.backend.chats import Chat, ChatSettings, DownloadState, UpdateChatParams
from dossier.backend.downloader_api import DownloaderApiClient
from dossier.backend.progress import ProgressHub
from dossier.downloader.api import ChatStateJson, DownloadStateJson


class BackendApi:
    def __init__(self, engine: Engine, hub: ProgressHub, downloader_api: DownloaderApiClient) -> None:
        self.engine = engine
        self.hub = hub
        self.downloader_api = downloader_api
        self.states: dict[int, DownloadState] = {}

    def read_chats(self) -> list[models.Chat]:
        with Session(self.engine) as session:
            return list(session.scalars(select(models.Chat).order_by(models.Chat.name)))

    def store_media_setting(self, chat_id: int, media: bool) -> models.Chat | None:
        with Session(self.engine, expire_on_commit=False) as session, session.begin():
            session.execute(update(models.Chat).where(models.Chat.chat_id == chat_id).values(download_media=media))
            return session.get(models.Chat, chat_id)

    def to_chat(self, row: models.Chat) -> Chat:
        return Chat(
            id=row.chat_id,
            name=row.name or "",
            settings=ChatSettings(media=bool(row.download_media)),
            state=self.states.get(row.chat_id, DownloadState()),
        )

    async def list_chats(self) -> Result:
        rows = await run_in_threadpool(self.read_chats)
        return Success({"chats": [self.to_chat(row).model_dump(mode="json") for row in rows]})

    async def update_chat(self, id: object, settings: object) -> Result:
        try:
            params = UpdateChatParams.model_validate({"id": id, "settings": settings})
        except ValidationError:
            return InvalidParams()
        row = await run_in_threadpool(self.store_media_setting, params.id, params.settings.media)
        if row is None:
            return Error(-32602, f"Chat {params.id} not found")
        await self.downloader_api.settings_changed(params.id)
        return Success(self.to_chat(row).model_dump(mode="json"))

    async def chat_states(self, chats: list[ChatStateJson]) -> Result:
        for chat in chats:
            await self.chat_download_progress(chat["id"], chat["state"])
        return Success(None)

    async def chat_download_progress(self, id: int, state: DownloadStateJson) -> Result:
        self.states[id] = DownloadState.model_validate(state)
        await self.hub.publish(id, self.states[id])
        return Success(None)
