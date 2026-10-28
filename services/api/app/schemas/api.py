from pydantic import BaseModel, Field, ConfigDict


class AgentInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    system_prompt: str = Field(
        default="You are a helpful voice assistant. Keep replies brief.",
        max_length=12000,
    )
    model: str = "gpt-4o-mini"
    voice_provider: str = Field(
        default="browser", pattern="^(browser|openai_realtime)$"
    )
    voice: str = ""
    language: str = Field(default="en-IN", pattern="^(en-IN|hi-IN|mr-IN)$")
    welcome_message: str = Field(
        default="Hello! How can I help you today?", max_length=1000
    )
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_duration: int = Field(default=300, ge=30, le=3600)
    active: bool = True


class AgentOut(AgentInput):
    id: int
    model_config = ConfigDict(from_attributes=True)


class Outbound(BaseModel):
    agent_id: int
    to: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    consent: bool


class Profile(BaseModel):
    name: str = Field(min_length=1, max_length=100)
