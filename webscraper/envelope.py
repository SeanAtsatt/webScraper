"""Canonical envelope schema for webscraper fetch results."""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

TierName = Literal["fast", "browser", "firecrawl"]
TierOutcome = Literal["success", "escalated", "failed"]
ImageRole = Literal["hero", "inline", "icon", "background"]
LinkKind = Literal["nav", "content", "external", "anchor"]


class TierAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier: TierName
    outcome: TierOutcome
    elapsed_ms: int = Field(ge=0)
    reason: str = ""


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tier_used: TierName
    tier_history: list[TierAttempt] = Field(min_length=1)
    http_status: int
    content_type: str
    auth_used: str = ""

    @model_validator(mode="after")
    def _tier_used_matches_last_history(self) -> "Meta":
        if self.tier_history[-1].tier != self.tier_used:
            raise ValueError("tier_used must equal tier_history[-1].tier")
        return self


class TableSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    headers: list[str] = []
    rows: list[list[str]] = []


class FormField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    label: str = ""


class FormSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = ""
    method: str = "GET"
    fields: list[FormField] = []


class ImageSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    alt: str = ""
    width: int = 0
    height: int = 0
    role: ImageRole = "inline"
    local_path: str = ""
    error: str = ""


class LinkSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    href: str
    text: str = ""
    rel: str = ""
    kind: LinkKind = "content"


class FetchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    final_url: str
    fetched_at: datetime
    meta: Meta
    title: str
    markdown: str
    text: str
    tables: list[TableSpec] = []
    forms: list[FormSpec] = []
    images: list[ImageSpec] = []
    links: list[LinkSpec] = []

    @field_validator("fetched_at")
    @classmethod
    def _fetched_at_must_be_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() != timedelta(0):
            raise ValueError("fetched_at must be timezone-aware UTC")
        return v.replace(microsecond=0)

    @field_serializer("fetched_at")
    def _serialize_fetched_at(self, dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
