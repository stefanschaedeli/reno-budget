"""Pydantic schemas for the AI Project Assistant.

Two distinct groups live here:

**Structured-output models** — the JSON shapes the LLM is *forced* to produce
(via the Anthropic structured-outputs feature). These are the contract between
``services/ai/skills`` and the model: the model retries until its output
validates against them, so the rest of the code never parses prose. Kept small
and flat because the structured-outputs feature does not support every JSON
Schema construct (no numeric ``minimum``/``maximum``, no recursion).

**API DTOs** — request/response bodies for ``api/v1/ai.py``.

Money is :class:`Decimal` (two decimals, CHF) as elsewhere in the codebase.
Confidence is a plain float in ``[0, 1]`` (validated in code, not schema, so the
LLM schema stays simple).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.ai import AiArtifactStatus, AiSessionStatus, AiStep

# ---------------------------------------------------------------------------
# Structured-output models (the LLM must conform to these)
# ---------------------------------------------------------------------------


class QuestionType(StrEnum):
    """How the wizard renders a generated question, and how the answer is typed."""

    NUMBER = "number"
    SELECT = "select"
    TEXT = "text"
    BOOLEAN = "boolean"


class Confidence(StrEnum):
    """Self-reported grounding confidence for a figure (Level-2 validation)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProjectClassification(BaseModel):
    """Output of the classify step.

    ``project_type`` is a short slug (e.g. ``"roof"``, ``"windows"``,
    ``"bathroom"``) the questioner uses to decide which questions matter.
    """

    project_type: str = Field(min_length=1, max_length=64)
    confidence: Confidence
    rationale: str = Field(max_length=2000)


class GeneratedQuestion(BaseModel):
    """One typed question the wizard renders as a real input.

    The LLM picks *which* questions to ask; this rigid shape lets the frontend
    render a number field with a unit, a select with options, etc., and lets the
    backend validate the answer against ``min``/``max``/``options``.
    """

    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=300)
    type: QuestionType
    unit: str | None = Field(default=None, max_length=32)
    help: str | None = Field(default=None, max_length=600)
    required: bool = True
    # ``min``/``max`` apply to NUMBER; ``options`` applies to SELECT.
    min: float | None = None
    max: float | None = None
    options: list[str] | None = None
    # Optional hint for which domain field this maps to (e.g. "area_m2").
    maps_to: str | None = Field(default=None, max_length=64)


class QuestionSet(BaseModel):
    """Output of the question step."""

    questions: list[GeneratedQuestion]


class EstimateLineItem(BaseModel):
    """One line of the rough cost estimate, self-grounded (Level 2)."""

    label: str = Field(min_length=1, max_length=300)
    amount_chf: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    assumptions: str = Field(max_length=2000)
    confidence: Confidence


class Estimate(BaseModel):
    """Output of the estimate step."""

    currency: str = Field(default="CHF", max_length=8)
    total_chf: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    line_items: list[EstimateLineItem]
    notes: str | None = Field(default=None, max_length=4000)


class BkpPosition(BaseModel):
    """One proposed BKP position with explicit in/out-of-scope detail."""

    bkp_code: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=200)
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    estimated_amount_chf: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    assumptions: str = Field(max_length=2000)
    confidence: Confidence


class BkpScope(BaseModel):
    """Output of the bkp_scope step."""

    positions: list[BkpPosition]


# ---------------------------------------------------------------------------
# Validation report (attached to each artifact)
# ---------------------------------------------------------------------------


class ValidationSeverity(StrEnum):
    """How seriously a validation finding should be surfaced."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationFinding(BaseModel):
    """A single deterministic (L1), grounding (L2), or critic (L3) finding."""

    layer: int = Field(ge=1, le=3)
    severity: ValidationSeverity
    message: str = Field(max_length=2000)
    # Optional pointer to the offending item (e.g. line-item label or bkp_code).
    target: str | None = Field(default=None, max_length=200)


class ValidationReport(BaseModel):
    """All findings for one artifact. ``ok`` is False if any ERROR is present."""

    ok: bool = True
    findings: list[ValidationFinding] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API DTOs
# ---------------------------------------------------------------------------


class AiArtifactRead(BaseModel):
    """Outbound view of a stored artifact (the step output + its report)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    step: AiStep
    status: AiArtifactStatus
    output: dict
    validation: dict
    created_at: datetime
    updated_at: datetime


class AiSessionRead(BaseModel):
    """Outbound view of a wizard session including its artifacts."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    object_id: uuid.UUID
    project_id: uuid.UUID
    status: AiSessionStatus
    project_type: str | None
    answers: dict
    created_at: datetime
    updated_at: datetime
    artifacts: list[AiArtifactRead] = Field(default_factory=list)


class AnswersSubmit(BaseModel):
    """Client submits typed answers gathered from the question step.

    Keys are :class:`GeneratedQuestion.key`; values are the typed answers
    (number / string / bool). Validated against the stored question set in the
    service layer.
    """

    answers: dict[str, object]


class RunStepRequest(BaseModel):
    """Trigger (or re-run) a single pipeline step."""

    step: AiStep
