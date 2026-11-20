from datetime import datetime

from pydantic import BaseModel, Field, StrictBool, StrictInt


class ChatSettings(BaseModel):
    media: StrictBool


class DownloadState(BaseModel):
    messages_count: int = 0
    oldest_message_date: datetime | None = None
    newest_message_date: datetime | None = None
    files_count: int = 0
    files_pending: int = 0
    downloaded: bool = False
    complete: bool | None = None


class Chat(BaseModel):
    id: int
    name: str
    settings: ChatSettings
    state: DownloadState = Field(default_factory=DownloadState)


class UpdateChatParams(BaseModel):
    id: StrictInt
    settings: ChatSettings
