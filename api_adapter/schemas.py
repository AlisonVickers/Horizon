from __future__ import annotations

from pydantic import BaseModel, Field


class ScenarioShock(BaseModel):
    name: str = Field(min_length=1)
    value: float = Field(ge=0)


class ScenarioRequest(BaseModel):
    shocks: list[ScenarioShock] = Field(default_factory=list)


class AssistantRequest(BaseModel):
    prompt: str = Field(min_length=1)


class AssistantResponse(BaseModel):
    message: str
    data: dict[str, object] = Field(default_factory=dict)
    tool_trace: list[str] = Field(default_factory=list)
