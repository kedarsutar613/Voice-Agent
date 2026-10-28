"""Initial VoiceOS schema (immutable revision)."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None


def upgrade():
    op.create_table(
        "ai_agents",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("voice_provider", sa.String(), nullable=False),
        sa.Column("voice", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("welcome_message", sa.String(), nullable=False),
        sa.Column("temperature", sa.Double(), nullable=False),
        sa.Column("max_duration", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_ai_agents_created_at", "ai_agents", ["created_at"], unique=False
    )
    op.create_table(
        "provider_settings",
        sa.Column("provider", sa.String(), nullable=False, unique=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_provider_settings_created_at",
        "provider_settings",
        ["created_at"],
        unique=False,
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_created_at", "users", ["created_at"], unique=False)
    op.create_table(
        "agent_settings",
        sa.Column(
            "agent_id",
            sa.Integer(),
            sa.ForeignKey("ai_agents.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_agent_settings_created_at", "agent_settings", ["created_at"], unique=False
    )
    op.create_table(
        "calls",
        sa.Column(
            "agent_id", sa.Integer(), sa.ForeignKey("ai_agents.id"), nullable=False
        ),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("caller_number", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("provider_sid", sa.String(), nullable=True, unique=True),
        sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_calls_status", "calls", ["status"], unique=False)
    op.create_index("ix_calls_created_at", "calls", ["created_at"], unique=False)
    op.create_index("ix_calls_agent_id", "calls", ["agent_id"], unique=False)
    op.create_table(
        "phone_numbers",
        sa.Column("number", sa.String(), nullable=False, unique=True),
        sa.Column(
            "agent_id", sa.Integer(), sa.ForeignKey("ai_agents.id"), nullable=False
        ),
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_phone_numbers_created_at", "phone_numbers", ["created_at"], unique=False
    )
    op.create_table(
        "call_recordings",
        sa.Column("call_id", sa.Integer(), sa.ForeignKey("calls.id"), nullable=False),
        sa.Column("provider_sid", sa.String(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_call_recordings_call_id", "call_recordings", ["call_id"], unique=False
    )
    op.create_index(
        "ix_call_recordings_created_at", "call_recordings", ["created_at"], unique=False
    )
    op.create_table(
        "conversations",
        sa.Column(
            "call_id",
            sa.Integer(),
            sa.ForeignKey("calls.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "agent_id", sa.Integer(), sa.ForeignKey("ai_agents.id"), nullable=False
        ),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_conversations_created_at", "conversations", ["created_at"], unique=False
    )
    op.create_index(
        "ix_conversations_agent_id", "conversations", ["agent_id"], unique=False
    )
    op.create_table(
        "messages",
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_messages_created_at", "messages", ["created_at"], unique=False)
    op.create_index(
        "ix_messages_conversation_id", "messages", ["conversation_id"], unique=False
    )


def downgrade():
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("call_recordings")
    op.drop_table("phone_numbers")
    op.drop_table("calls")
    op.drop_table("agent_settings")
    op.drop_table("users")
    op.drop_table("provider_settings")
    op.drop_table("ai_agents")
