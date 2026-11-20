from fastapi.concurrency import run_in_threadpool
from jsonrpcserver import Error, InvalidParams, Result, Success
from pydantic import ValidationError
from sqlalchemy import ColumnElement, Engine, func, select
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

    def read_chats(self, *conditions: ColumnElement[bool]) -> list[Chat]:
        statement = (
            select(
                models.Chat,
                func.count(models.Message.id),
                func.min(models.Message.date),
                func.max(models.Message.date),
                func.count(models.Message.media_path),
                func.count(models.Message.id).filter(models.file_pending()),
            )
            .outerjoin(models.Message, models.Message.chat_id == models.Chat.chat_id)
            .where(*conditions)
            .group_by(models.Chat.chat_id)
        )
        with Session(self.engine) as session:
            return [self.to_chat(*row) for row in session.execute(statement)]

    def store_media_setting(self, chat_id: int, media: bool) -> bool:
        with Session(self.engine) as session, session.begin():
            chat = session.get(models.Chat, chat_id)
            if chat is None:
                return False
            chat.download_media = media
        return True

    def to_chat(
        self,
        row: models.Chat,
        messages_count: int,
        oldest_message_date: str | None,
        newest_message_date: str | None,
        files_count: int,
        files_pending: int,
    ) -> Chat:
        state = self.states.get(row.chat_id)
        if state is None:
            state = DownloadState.model_validate(
                {
                    "messages_count": messages_count,
                    "oldest_message_date": oldest_message_date,
                    "newest_message_date": newest_message_date,
                    "files_count": files_count,
                    "files_pending": files_pending,
                    "downloaded": row.downloaded,
                }
            )
        return Chat(
            id=row.chat_id,
            name=row.name,
            settings=ChatSettings(media=row.download_media),
            state=state,
        )

    async def list_chats(self) -> Result:
        chats = await run_in_threadpool(self.read_chats)
        return Success({"chats": [chat.model_dump(mode="json") for chat in chats]})

    async def update_chat(self, id: object, settings: object) -> Result:
        try:
            params = UpdateChatParams.model_validate({"id": id, "settings": settings})
        except ValidationError:
            return InvalidParams()
        if not await run_in_threadpool(self.store_media_setting, params.id, params.settings.media):
            return Error(-32602, f"Chat {params.id} not found")
        await self.downloader_api.settings_changed(params.id)
        chats = await run_in_threadpool(self.read_chats, models.Chat.chat_id == params.id)
        return Success(chats[0].model_dump(mode="json"))

    async def downloader_disconnected(self) -> None:
        chat_ids = list(self.states)
        self.states.clear()
        for chat in await run_in_threadpool(self.read_chats, models.Chat.chat_id.in_(chat_ids)):
            await self.hub.publish(chat.id, chat.state)

    async def chat_states(self, chats: list[ChatStateJson]) -> Result:
        for chat in chats:
            await self.chat_download_progress(chat["id"], chat["state"])
        return Success(None)

    async def chat_download_progress(self, id: int, state: DownloadStateJson) -> Result:
        self.states[id] = DownloadState.model_validate(state)
        await self.hub.publish(id, self.states[id])
        return Success(None)
