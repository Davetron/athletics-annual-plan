"""
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# Auth schemas
class ValidateCodeRequest(BaseModel):
    """Request to validate an invite code."""

    code: str = Field(..., min_length=1, max_length=50)


class ValidateCodeResponse(BaseModel):
    """Response from validating an invite code."""

    valid: bool
    session_id: str | None = None
    remaining_uses: int | None = None
    error: str | None = None


# Chat schemas
class ChatMessage(BaseModel):
    """A single chat message."""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    """Request to chat with Claude."""

    system: str | None = None
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    """Response from Claude chat."""

    content: list[dict[str, Any]]
    model: str | None = None
    stop_reason: str | None = None


# Plan generation schemas
class FormData(BaseModel):
    """Athlete/plan form data."""

    athleteName: str = Field(..., alias="athleteName")
    eventGroup: str = Field(..., alias="eventGroup")
    season: str
    periodization: str
    ageGroups: list[str] | None = Field(None, alias="ageGroups")
    trainingLevel: str | None = Field(None, alias="trainingLevel")
    country: str | None = None
    compLevels: list[str] | None = Field(None, alias="compLevels")
    targetCompetitions: str | None = Field(None, alias="targetCompetitions")


class GeneratePlanRequest(BaseModel):
    """Request to generate a training plan."""

    formData: FormData
    messages: list[ChatMessage] | None = None


class Competition(BaseModel):
    """A competition in the plan."""

    name: str
    date: str
    weekNum: int = Field(..., ge=1, le=52)
    importance: int = Field(..., ge=1, le=3)


class Week(BaseModel):
    """A single week in the training plan."""

    weekNum: int = Field(..., ge=1, le=52)
    startDate: str
    month: str
    phase: str
    phaseType: str
    block: str | None = None
    load: int = Field(..., ge=0, le=4)
    competitions: list[str] | None = None
    competitionImportance: int | None = None
    technical: str | None = None
    physical: str | None = None


class Plan(BaseModel):
    """Complete 52-week training plan."""

    athlete: str
    season: str
    eventGroup: str
    periodization: str
    trainingLevel: str | None = None
    seasonStart: str
    competitions: list[Competition]
    weeks: list[Week] = Field(..., min_length=52, max_length=52)


class GeneratePlanResponse(BaseModel):
    """Response containing the generated plan."""

    success: bool
    plan: Plan | None = None
    error: str | None = None


# URL fetch schemas
class FetchUrlRequest(BaseModel):
    """Request to fetch a URL."""

    url: str


class FetchUrlResponse(BaseModel):
    """Response from fetching a URL."""

    success: bool
    url: str | None = None
    content: str | None = None
    truncated: bool = False
    original_length: int | None = None
    error: str | None = None


# Competition search schemas
class SearchCompetitionsRequest(BaseModel):
    """Request to search for competitions."""

    country: str = "Ireland"
    athlete_type: str = "Senior"
    season_year: str
    include_european: bool = True
    include_world: bool = False


class CompetitionResult(BaseModel):
    """A competition found via search."""

    name: str
    date: str
    end_date: str | None = None
    location: str | None = None
    importance: int = 3
    type: str | None = None


class SearchCompetitionsResponse(BaseModel):
    """Response containing found competitions."""

    success: bool
    competitions: list[CompetitionResult] = []
    error: str | None = None


# Excel download schemas
class DownloadExcelRequest(BaseModel):
    """Request to download plan as Excel."""

    plan: Plan
