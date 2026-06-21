"""Describe step — produce an improved project description from gathered answers."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.services.ai.client import AiClient
from app.services.ai.prompts import SYSTEM_PROMPT


class DescriptionDraft(BaseModel):
    """Structured output of the describe step."""

    description: str = Field(min_length=1, max_length=4000)


def build_prompt(
    name: str, current: str | None, answers: dict[str, Any]
) -> str:
    return (
        "Write an improved, concise German description of this renovation "
        "project for a budgeting tool: what will be done and the relevant scope. "
        "Use the gathered answers. Do not invent facts not implied by them.\n\n"
        f"Project name: {name}\n"
        f"Current description: {current or '(none)'}\n"
        f"Answers: {json.dumps(answers, ensure_ascii=False)}\n"
    )


async def describe(
    client: AiClient,
    *,
    name: str,
    current: str | None,
    answers: dict[str, Any],
) -> DescriptionDraft:
    return await client.generate(
        system=SYSTEM_PROMPT,
        prompt=build_prompt(name, current, answers),
        schema=DescriptionDraft,
    )
