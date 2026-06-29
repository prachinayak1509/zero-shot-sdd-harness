from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str
    conversation_id: int | None = None


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    min: Any | None = None
    max: Any | None = None
    null_count: int


class DatasetProfile(BaseModel):
    columns: list[ColumnProfile]
    row_count: int
    sample: list[dict[str, Any]]


class DatasetResponse(BaseModel):
    id: int
    name: str
    row_count: int
    profile: dict[str, Any]


class AskResponse(BaseModel):
    conversation_id: int
    audit_id: int
    answer: str | None = None
    code: str | None = None
    result_repr: str | None = None
    effort: str | None = None
    step_count: int = 0
    status: str = "completed"
    tokens_used: int = 0
    chart_spec: Any | None = None
    table: Any | None = None
    follow_ups: list[str] | None = None
    steps: list[dict[str, Any]] | None = None
