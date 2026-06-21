"""Level-3 validation: a second-model critic pass over cost/BKP drafts.

After the deterministic (L1) and grounding (L2) checks pass, the estimate and
BKP-scope drafts are sent to a *different*, cheaper model (Sonnet 4.6) with an
adversarial prompt: find what is unrealistic, internally inconsistent, or out of
scope. The critic's findings are merged into the artifact's
:class:`~app.schemas.ai.ValidationReport` as ``layer=3`` items.

The critic is advisory — its findings default to ``WARNING`` so they surface to
the user for review rather than silently blocking the draft. This keeps a single
disagreeing model from hard-failing an otherwise sound estimate; the human makes
the call.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.ai import (
    BkpScope,
    Estimate,
    ValidationFinding,
    ValidationReport,
    ValidationSeverity,
)
from app.services.ai.client import CRITIC_MODEL, AiClient

_CRITIC_SYSTEM = """\
You are a critical reviewer of Swiss renovation cost estimates and eBKP-H scope
breakdowns. Your job is to find problems: figures that are unrealistic for
Switzerland, line items that don't add up, scope that is missing or wrong, and
positions that look padded or implausible. Be specific and concise. If the draft
looks sound, return an empty issue list. Respond in German.
"""


class CriticIssue(BaseModel):
    """One problem the critic found."""

    message: str = Field(max_length=2000)
    target: str | None = Field(default=None, max_length=200)


class CriticVerdict(BaseModel):
    """Structured critic output."""

    issues: list[CriticIssue] = Field(default_factory=list)


def _to_findings(verdict: CriticVerdict) -> list[ValidationFinding]:
    return [
        ValidationFinding(
            layer=3,
            severity=ValidationSeverity.WARNING,
            message=issue.message,
            target=issue.target,
        )
        for issue in verdict.issues
    ]


async def critique_estimate(client: AiClient, est: Estimate) -> list[ValidationFinding]:
    verdict = await client.generate(
        system=_CRITIC_SYSTEM,
        prompt=(
            "Review this cost estimate. List concrete problems.\n\n"
            + est.model_dump_json(indent=2)
        ),
        schema=CriticVerdict,
        model=CRITIC_MODEL,
    )
    return _to_findings(verdict)


async def critique_bkp_scope(client: AiClient, scope: BkpScope) -> list[ValidationFinding]:
    verdict = await client.generate(
        system=_CRITIC_SYSTEM,
        prompt=(
            "Review this eBKP-H scope breakdown. List concrete problems.\n\n"
            + scope.model_dump_json(indent=2)
        ),
        schema=CriticVerdict,
        model=CRITIC_MODEL,
    )
    return _to_findings(verdict)


def merge_findings(
    report: ValidationReport, critic_findings: list[ValidationFinding]
) -> ValidationReport:
    """Return a new report with critic findings appended (ok unchanged — L3 warns)."""
    return ValidationReport(
        ok=report.ok,
        findings=[*report.findings, *critic_findings],
    )
