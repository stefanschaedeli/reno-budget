"""Unit tests for the AI assistant deterministic (L1) + grounding (L2) validators.

These run on every LLM output before it is shown to the user. They are pure
functions over the parsed structured-output models — no DB, no network — so
they are cheap to exercise exhaustively. The catalogue-existence check takes the
set of known BKP codes as a plain argument (the service layer supplies it).
"""

from __future__ import annotations

from decimal import Decimal

from app.schemas.ai import (
    BkpPosition,
    BkpScope,
    Confidence,
    Estimate,
    EstimateLineItem,
    GeneratedQuestion,
    QuestionSet,
    QuestionType,
    ValidationSeverity,
)
from app.services.ai.validators import (
    DEFAULT_MAX_CHF_PER_M2,
    validate_bkp_scope,
    validate_estimate,
    validate_question_set,
)


def _line(label: str, amount: str, conf: Confidence = Confidence.HIGH) -> EstimateLineItem:
    return EstimateLineItem(
        label=label, amount_chf=Decimal(amount), assumptions="x", confidence=conf
    )


def _position(code: str, amount: str = "1000.00") -> BkpPosition:
    return BkpPosition(
        bkp_code=code,
        title="Dach",
        in_scope=["Ziegel"],
        out_of_scope=["Gerüst"],
        estimated_amount_chf=Decimal(amount),
        assumptions="x",
        confidence=Confidence.HIGH,
    )


class TestValidateEstimate:
    def test_consistent_estimate_passes(self) -> None:
        est = Estimate(
            total_chf=Decimal("300.00"),
            line_items=[_line("a", "100.00"), _line("b", "200.00")],
        )
        report = validate_estimate(est)
        assert report.ok is True
        assert report.findings == []

    def test_line_items_not_summing_to_total_is_error(self) -> None:
        est = Estimate(
            total_chf=Decimal("999.00"),
            line_items=[_line("a", "100.00"), _line("b", "200.00")],
        )
        report = validate_estimate(est)
        assert report.ok is False
        assert any(
            f.severity is ValidationSeverity.ERROR and f.layer == 1
            for f in report.findings
        )

    def test_low_confidence_line_item_is_warning_not_error(self) -> None:
        est = Estimate(
            total_chf=Decimal("100.00"),
            line_items=[_line("a", "100.00", Confidence.LOW)],
        )
        report = validate_estimate(est)
        # L2 grounding flag does not block — it warns.
        assert report.ok is True
        assert any(
            f.severity is ValidationSeverity.WARNING and f.layer == 2
            for f in report.findings
        )

    def test_zero_total_with_no_items_is_error(self) -> None:
        est = Estimate(total_chf=Decimal("0.00"), line_items=[])
        report = validate_estimate(est)
        assert report.ok is False

    def test_implausible_cost_per_m2_is_warning(self) -> None:
        # 5000 CHF/m² over 100 m² = 500k, far above the sane band.
        over = Decimal(DEFAULT_MAX_CHF_PER_M2) * Decimal("100") * Decimal("2")
        est = Estimate(
            total_chf=over,
            line_items=[_line("Dachfläche", str(over))],
        )
        report = validate_estimate(est, area_m2=100.0)
        assert any(
            f.severity is ValidationSeverity.WARNING and "m²" in f.message
            for f in report.findings
        )


class TestValidateBkpScope:
    def test_all_codes_known_passes(self) -> None:
        scope = BkpScope(positions=[_position("D5.01"), _position("E1.02")])
        report = validate_bkp_scope(scope, known_codes={"D5.01", "E1.02"})
        assert report.ok is True

    def test_unknown_code_is_error(self) -> None:
        scope = BkpScope(positions=[_position("ZZ.99")])
        report = validate_bkp_scope(scope, known_codes={"D5.01"})
        assert report.ok is False
        assert any(
            f.layer == 1
            and f.severity is ValidationSeverity.ERROR
            and f.target == "ZZ.99"
            for f in report.findings
        )

    def test_empty_positions_is_error(self) -> None:
        scope = BkpScope(positions=[])
        report = validate_bkp_scope(scope, known_codes={"D5.01"})
        assert report.ok is False

    def test_low_confidence_position_is_warning(self) -> None:
        pos = _position("D5.01")
        pos.confidence = Confidence.LOW
        scope = BkpScope(positions=[pos])
        report = validate_bkp_scope(scope, known_codes={"D5.01"})
        assert report.ok is True
        assert any(f.layer == 2 for f in report.findings)


class TestValidateQuestionSet:
    def test_well_formed_questions_pass(self) -> None:
        qs = QuestionSet(
            questions=[
                GeneratedQuestion(
                    key="area_m2", label="Fläche?", type=QuestionType.NUMBER, unit="m²"
                ),
                GeneratedQuestion(
                    key="insulation",
                    label="Dämmung?",
                    type=QuestionType.SELECT,
                    options=["Standard", "Hoch"],
                ),
            ]
        )
        report = validate_question_set(qs)
        assert report.ok is True

    def test_select_without_options_is_error(self) -> None:
        qs = QuestionSet(
            questions=[
                GeneratedQuestion(key="x", label="?", type=QuestionType.SELECT)
            ]
        )
        report = validate_question_set(qs)
        assert report.ok is False

    def test_duplicate_keys_is_error(self) -> None:
        qs = QuestionSet(
            questions=[
                GeneratedQuestion(key="dup", label="a", type=QuestionType.TEXT),
                GeneratedQuestion(key="dup", label="b", type=QuestionType.TEXT),
            ]
        )
        report = validate_question_set(qs)
        assert report.ok is False

    def test_empty_question_set_is_error(self) -> None:
        report = validate_question_set(QuestionSet(questions=[]))
        assert report.ok is False
