"""BKP scope step — propose eBKP-H positions with in/out-of-scope detail.

The model is given ONLY the relevant catalogue subset and must choose codes from
it; the deterministic validator independently rejects any hallucinated code.
Uses adaptive thinking (the second hard step).
"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.ai import BkpScope
from app.services.ai.client import AiClient
from app.services.ai.prompts import SYSTEM_PROMPT


def build_prompt(
    project_type: str,
    name: str,
    description: str | None,
    answers: dict[str, Any],
    catalogue: list[dict[str, str]],
) -> str:
    return (
        "Propose the eBKP-H (BKP) cost positions for this renovation. For each "
        "position give the bkp_code (ONLY from the catalogue below), a German "
        "title, explicit in-scope and out-of-scope bullet lists, an estimated "
        "amount in CHF, your assumptions, and a confidence rating.\n\n"
        f"Project type: {project_type}\n"
        f"Project name: {name}\n"
        f"Description: {description or '(none)'}\n"
        f"Answers: {json.dumps(answers, ensure_ascii=False)}\n\n"
        "Allowed BKP catalogue (code: label):\n"
        + "\n".join(f"  {c['code']}: {c['label_de']}" for c in catalogue)
        + "\n"
    )


async def scope_bkp(
    client: AiClient,
    *,
    project_type: str,
    name: str,
    description: str | None,
    answers: dict[str, Any],
    catalogue: list[dict[str, str]],
) -> BkpScope:
    return await client.generate(
        system=SYSTEM_PROMPT,
        prompt=build_prompt(project_type, name, description, answers, catalogue),
        schema=BkpScope,
        thinking=True,
    )
