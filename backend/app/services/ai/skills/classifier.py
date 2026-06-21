"""Classify step — map a project's name/description to a project type slug."""

from __future__ import annotations

from app.schemas.ai import ProjectClassification
from app.services.ai.client import AiClient
from app.services.ai.prompts import SYSTEM_PROMPT


def build_prompt(name: str, description: str | None) -> str:
    return (
        "Classify this renovation project into a short snake_case project_type "
        "slug (e.g. roof, windows, bathroom, facade, heating, electrical).\n\n"
        f"Project name: {name}\n"
        f"Project description: {description or '(none)'}\n"
    )


async def classify(
    client: AiClient, *, name: str, description: str | None
) -> ProjectClassification:
    return await client.generate(
        system=SYSTEM_PROMPT,
        prompt=build_prompt(name, description),
        schema=ProjectClassification,
    )
