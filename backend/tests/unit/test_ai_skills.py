"""Unit tests for AI skills + critic with a fake client (no live API).

The fake records the (system, prompt, schema, thinking, model) of each call and
returns a caller-supplied canned model instance, so we can assert that each skill
builds the right prompt, requests the right schema, and uses thinking/critic
model where the design requires it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.schemas.ai import (
    BkpPosition,
    BkpScope,
    Confidence,
    Estimate,
    EstimateLineItem,
    GeneratedQuestion,
    ProjectClassification,
    QuestionSet,
    QuestionType,
)
from app.services.ai import critic
from app.services.ai.client import CRITIC_MODEL
from app.services.ai.critic import CriticIssue, CriticVerdict
from app.services.ai.skills import (
    bkp_scoper,
    classifier,
    describer,
    estimator,
    questioner,
)
from pydantic import BaseModel


class FakeClient:
    """Stand-in for AiClient.generate that returns queued canned results."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._queue: list[BaseModel] = []

    def queue(self, result: BaseModel) -> None:
        self._queue.append(result)

    async def generate(
        self, *, system, prompt, schema, thinking=False, model=None
    ):
        self.calls.append(
            {
                "system": system,
                "prompt": prompt,
                "schema": schema,
                "thinking": thinking,
                "model": model,
            }
        )
        return self._queue.pop(0)


@pytest.fixture
def fake() -> FakeClient:
    return FakeClient()


async def test_classifier_requests_classification_schema(fake: FakeClient) -> None:
    fake.queue(
        ProjectClassification(
            project_type="roof", confidence=Confidence.HIGH, rationale="x"
        )
    )
    result = await classifier.classify(fake, name="Dach erneuern", description=None)
    assert result.project_type == "roof"
    call = fake.calls[0]
    assert call["schema"] is ProjectClassification
    assert call["thinking"] is False
    assert "Dach erneuern" in call["prompt"]


async def test_questioner_requests_question_set(fake: FakeClient) -> None:
    fake.queue(
        QuestionSet(
            questions=[
                GeneratedQuestion(
                    key="area_m2", label="Fläche?", type=QuestionType.NUMBER
                )
            ]
        )
    )
    result = await questioner.generate_questions(
        fake, project_type="roof", name="Dach", description=None
    )
    assert result.questions[0].key == "area_m2"
    assert fake.calls[0]["schema"] is QuestionSet
    assert "roof" in fake.calls[0]["prompt"]


async def test_describer_includes_answers_in_prompt(fake: FakeClient) -> None:
    fake.queue(describer.DescriptionDraft(description="Neues Dach"))
    result = await describer.describe(
        fake, name="Dach", current=None, answers={"area_m2": 120}
    )
    assert result.description == "Neues Dach"
    assert "area_m2" in fake.calls[0]["prompt"]


async def test_estimator_uses_thinking(fake: FakeClient) -> None:
    fake.queue(
        Estimate(
            total_chf=Decimal("100.00"),
            line_items=[
                EstimateLineItem(
                    label="a",
                    amount_chf=Decimal("100.00"),
                    assumptions="x",
                    confidence=Confidence.HIGH,
                )
            ],
        )
    )
    await estimator.estimate(
        fake, project_type="roof", name="Dach", description=None, answers={}
    )
    assert fake.calls[0]["thinking"] is True


async def test_bkp_scoper_passes_catalogue_and_uses_thinking(fake: FakeClient) -> None:
    fake.queue(
        BkpScope(
            positions=[
                BkpPosition(
                    bkp_code="D5.01",
                    title="Dach",
                    estimated_amount_chf=Decimal("1000.00"),
                    assumptions="x",
                    confidence=Confidence.HIGH,
                )
            ]
        )
    )
    await bkp_scoper.scope_bkp(
        fake,
        project_type="roof",
        name="Dach",
        description=None,
        answers={},
        catalogue=[{"code": "D5.01", "label_de": "Dachbelag"}],
    )
    call = fake.calls[0]
    assert call["thinking"] is True
    assert "D5.01" in call["prompt"]  # catalogue subset is in the prompt


async def test_critic_uses_critic_model_and_emits_layer3(fake: FakeClient) -> None:
    fake.queue(CriticVerdict(issues=[CriticIssue(message="zu teuer", target="a")]))
    est = Estimate(
        total_chf=Decimal("100.00"),
        line_items=[
            EstimateLineItem(
                label="a",
                amount_chf=Decimal("100.00"),
                assumptions="x",
                confidence=Confidence.HIGH,
            )
        ],
    )
    findings = await critic.critique_estimate(fake, est)
    assert fake.calls[0]["model"] == CRITIC_MODEL
    assert len(findings) == 1
    assert findings[0].layer == 3


def test_merge_findings_preserves_ok() -> None:
    from app.schemas.ai import ValidationReport

    base = ValidationReport(ok=True, findings=[])
    merged = critic.merge_findings(
        base, [critic._to_findings(CriticVerdict(issues=[CriticIssue(message="m")]))[0]]
    )
    assert merged.ok is True
    assert len(merged.findings) == 1
    assert merged.findings[0].layer == 3
