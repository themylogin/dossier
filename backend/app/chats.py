from datetime import UTC, datetime

from pydantic import BaseModel, Field, StrictBool, StrictInt


class ChatSettings(BaseModel):
    media: StrictBool


class DownloadState(BaseModel):
    messages_count: int = 0
    oldest_message_date: datetime | None = None
    newest_message_date: datetime | None = None
    complete: bool = False


class Chat(BaseModel):
    id: int
    name: str
    first_message_date: datetime = Field(exclude=True)
    settings: ChatSettings = Field(default_factory=lambda: ChatSettings(media=False))
    state: DownloadState = Field(default_factory=DownloadState)


class UpdateChatParams(BaseModel):
    id: StrictInt
    settings: ChatSettings


def fake_chats() -> dict[int, Chat]:
    chats = [
        Chat(id=1001, name="Alice Smith", first_message_date=datetime(2023, 3, 14, 9, 26, 53, tzinfo=UTC)),
        Chat(id=1002, name="Bob Jones", first_message_date=datetime(2024, 7, 1, 18, 4, 11, tzinfo=UTC)),
        Chat(id=-2001, name="Family", first_message_date=datetime(2021, 11, 5, 7, 45, tzinfo=UTC)),
        Chat(id=-2002, name="Book Club", first_message_date=datetime(2025, 2, 10, 12, 30, tzinfo=UTC)),
    ]
    return {chat.id: chat for chat in chats}
