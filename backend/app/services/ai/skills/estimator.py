"""Estimate step — produce a rough, self-grounded cost estimate.

Uses adaptive thinking (this is one of the two hard, numeric steps). Each line
item carries assumptions + confidence (Level-2 grounding) which the validators
and the wizard surface to the user.
"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.ai import Estimate
from app.services.ai.client import AiClient
from app.services.ai.prompts import SYSTEM_PROMPT


def build_prompt(
    project_type: str, name: str, description: str | None, answers: dict[str, Any]
) -> str:
    return (
        "Produce a ROUGH cost estimate in CHF for this renovation, broken into a "
        "few line items. For every figure, state the assumptions and rate your "
        "confidence (low/medium/high). The line items must sum to the total. "
        "These are planning figures for Switzerland, not a quote.\n\n"
        f"Project type: {project_type}\n"
        f"Project name: {name}\n"
        f"Description: {description or '(none)'}\n"
        f"Answers: {json.dumps(answers, ensure_ascii=False)}\n"
    )


async def estimate(
    client: AiClient,
    *,
    project_type: str,
    name: str,
    description: str | None,
    answers: dict[str, Any],
) -> Estimate:
    return await client.generate(
        system=SYSTEM_PROMPT,
        prompt=build_prompt(project_type, name, description, answers),
        schema=Estimate,
        thinking=True,
    )
