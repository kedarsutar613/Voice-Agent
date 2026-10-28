from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base


class Stamp:
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class User(Stamp, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str]
    name: Mapped[str] = mapped_column(default="Administrator")
    role: Mapped[str] = mapped_column(default="admin")


class AIAgent(Stamp, Base):
    __tablename__ = "ai_agents"
    name: Mapped[str]
    description: Mapped[str] = mapped_column(default="")
    system_prompt: Mapped[str] = mapped_column(
        Text, default="You are a helpful voice assistant. Keep replies brief."
    )
    model: Mapped[str] = mapped_column(default="gpt-4o-mini")
    voice_provider: Mapped[str] = mapped_column(default="browser")
    voice: Mapped[str] = mapped_column(default="")
    language: Mapped[str] = mapped_column(default="en-IN")
    welcome_message: Mapped[str] = mapped_column(
        default="Hello! How can I help you today?"
    )
    temperature: Mapped[float] = mapped_column(default=0.7)
    max_duration: Mapped[int] = mapped_column(default=300)
    active: Mapped[bool] = mapped_column(default=True)


class Call(Stamp, Base):
    __tablename__ = "calls"
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"), index=True)
    direction: Mapped[str]
    caller_number: Mapped[str] = mapped_column(default="Browser")
    status: Mapped[str] = mapped_column(default="active", index=True)
    duration: Mapped[int] = mapped_column(default=0)
    provider_sid: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    consent: Mapped[bool] = mapped_column(default=False)


class Conversation(Stamp, Base):
    __tablename__ = "conversations"
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), unique=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"), index=True)
    language: Mapped[str]
    messages: Mapped[list["Message"]] = relationship(
        cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(Stamp, Base):
    __tablename__ = "messages"
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), index=True
    )
    role: Mapped[str]
    content: Mapped[str] = mapped_column(Text)


class PhoneNumber(Stamp, Base):
    __tablename__ = "phone_numbers"
    number: Mapped[str] = mapped_column(unique=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"))


class CallRecording(Stamp, Base):
    __tablename__ = "call_recordings"
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), index=True)
    provider_sid: Mapped[str]


class AgentSettings(Stamp, Base):
    __tablename__ = "agent_settings"
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"), unique=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)


class ProviderSettings(Stamp, Base):
    __tablename__ = "provider_settings"
    provider: Mapped[str] = mapped_column(unique=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
