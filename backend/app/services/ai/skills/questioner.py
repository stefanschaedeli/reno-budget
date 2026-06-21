"""Question step — generate the typed questions that matter for a project type.

The model chooses *which* questions to ask; the :class:`QuestionSet` schema
forces each into a typed field the wizard can render and validate.
"""

from __future__ import annotations

from app.schemas.ai import QuestionSet
from app.services.ai.client import AiClient
from app.services.ai.prompts import SYSTEM_PROMPT


def build_prompt(project_type: str, name: str, description: str | None) -> str:
    return (
        "Generate the small set of questions whose answers most affect the cost "
        f"and scope of a '{project_type}' renovation. Ask only what matters "
        "(e.g. roof -> area in m²; windows -> count + insulation/security level). "
        "Each question must be a typed field: number (with unit, min, max), "
        "select (with options), boolean, or text. Questions and labels in German.\n\n"
        f"Project name: {name}\n"
        f"Project description: {description or '(none)'}\n"
    )


async def generate_questions(
    client: AiClient,
    *,
    project_type: str,
    name: str,
    description: str | None,
) -> QuestionSet:
    return await client.generate(
        system=SYSTEM_PROMPT,
        prompt=build_prompt(project_type, name, description),
        schema=QuestionSet,
    )
