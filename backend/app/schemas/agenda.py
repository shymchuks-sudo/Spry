from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgendaItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    topic: str = Field(min_length=1, max_length=300)
    owner: str | None = Field(default=None, max_length=200)
    minutes: int | None = Field(default=None, ge=1, le=480)


class ActionItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    task: str = Field(min_length=1, max_length=300)
    owner: str | None = Field(default=None, max_length=200)
    due: date | None = None


class AgendaSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgendaItemIn] = Field(min_length=1, max_length=50)
    action_items: list[ActionItemIn] = Field(default_factory=list, max_length=50)
    ai_suggestion: dict[str, Any] | None = None
    ai_model: str | None = Field(default=None, max_length=100)
    prompt_version: str | None = Field(default=None, max_length=50)


class AgendaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    meeting_id: int
    content: dict[str, Any]
    ai_suggestion: dict[str, Any] | None
    ai_model: str | None
    prompt_version: str | None
    created_at: datetime
