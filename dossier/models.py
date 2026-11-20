from sqlalchemy import Boolean, ColumnElement, Index, Integer, Text, UniqueConstraint, and_
from sqlalchemy import text as sql_text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("chat_id", "message_id"),
        Index("idx_chat_message", "chat_id", "message_id"),
        Index("idx_date", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    sender_id: Mapped[int | None] = mapped_column(Integer)
    grouped_id: Mapped[int | None] = mapped_column(Integer)
    has_media: Mapped[bool] = mapped_column(Boolean)
    media_type: Mapped[str | None] = mapped_column(Text)
    media_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, server_default=sql_text("CURRENT_TIMESTAMP"))
    edit_date: Mapped[str | None] = mapped_column(Text)
    media_id: Mapped[int | None] = mapped_column(Integer)
    media_replaced_at: Mapped[str | None] = mapped_column(Text)


class MessageVersion(Base):
    __tablename__ = "message_versions"
    __table_args__ = (UniqueConstraint("chat_id", "message_id", "version_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer)
    message_id: Mapped[int] = mapped_column(Integer)
    version_date: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    has_media: Mapped[bool] = mapped_column(Boolean)
    media_type: Mapped[str | None] = mapped_column(Text)
    media_path: Mapped[str | None] = mapped_column(Text)
    media_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(Text, server_default=sql_text("CURRENT_TIMESTAMP"))


class Chat(Base):
    __tablename__ = "chats"

    chat_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    username: Mapped[str | None] = mapped_column(Text)
    download_media: Mapped[bool] = mapped_column(Boolean)
    downloaded: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("0"))


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    is_bot: Mapped[bool] = mapped_column(Boolean)


def file_pending() -> ColumnElement[bool]:
    return and_(Message.has_media, Message.media_path.is_(None), Message.media_type.is_distinct_from("other"))
