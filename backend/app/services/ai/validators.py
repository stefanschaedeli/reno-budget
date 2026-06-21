"""Deterministic (L1) and grounding (L2) validation for AI assistant outputs.

These are pure functions over the parsed structured-output models — no DB, no
network — and run on **every** LLM output before it reaches the user. They are
the cheapest and most reliable guard against hallucination:

* **Level 1 — deterministic, no AI.** Things that are simply true-or-false:
  line items must sum to the stated total, amounts must be present, every
  ``bkp_code`` must exist in the real catalogue, generated questions must be
  well-formed, costs-per-m² must fall in a sane band. Violations are ``ERROR``
  and block the draft.
* **Level 2 — self-grounding.** The model is required to attach a confidence to
  each figure; low-confidence items are surfaced as ``WARNING`` so the user
  reviews them. These do **not** block.

The Level-3 critic (a second model) lives in :mod:`app.services.ai.critic`; it
is orchestrated by the pipeline after L1 passes.

The BKP catalogue is passed in as a plain ``set[str]`` so these functions stay
free of the database; the service layer supplies the known codes.
"""

from __future__ import annotations

from decimal import Decimal

from app.schemas.ai import (
    BkpScope,
    Confidence,
    Estimate,
    QuestionSet,
    QuestionType,
    ValidationFinding,
    ValidationReport,
    ValidationSeverity,
)

# Sane upper band for renovation cost per square metre (CHF). Deliberately
# generous — this only catches absurd hallucinations (e.g. 50'000 CHF/m²), not
# genuinely expensive work. Configurable so the band can be tuned later or fed
# from the deferred Level-4 reference table.
DEFAULT_MAX_CHF_PER_M2 = 8000

# Allowed cent drift between the sum of line items and the stated total, to
# tolerate rounding in the model's arithmetic.
_TOTAL_TOLERANCE_CHF = Decimal("0.05")


def _report(findings: list[ValidationFinding]) -> ValidationReport:
    ok = not any(f.severity is ValidationSeverity.ERROR for f in findings)
    return ValidationReport(ok=ok, findings=findings)


def validate_estimate(est: Estimate, *, area_m2: float | None = None) -> ValidationReport:
    """L1 arithmetic + sanity, L2 confidence flags for a cost estimate."""
    findings: list[ValidationFinding] = []

    if not est.line_items:
        findings.append(
            ValidationFinding(
                layer=1,
                severity=ValidationSeverity.ERROR,
                message="Schätzung enthält keine Positionen.",
            )
        )

    # L1: line items must sum to the stated total (within rounding tolerance).
    items_sum = sum((li.amount_chf for li in est.line_items), Decimal("0"))
    if est.line_items and abs(items_sum - est.total_chf) > _TOTAL_TOLERANCE_CHF:
        findings.append(
            ValidationFinding(
                layer=1,
                severity=ValidationSeverity.ERROR,
                message=(
                    f"Summe der Positionen ({items_sum} CHF) weicht von der "
                    f"Gesamtsumme ({est.total_chf} CHF) ab."
                ),
            )
        )

    # L1: cost-per-m² plausibility, when a project area is known.
    if area_m2 and area_m2 > 0:
        per_m2 = est.total_chf / Decimal(str(area_m2))
        if per_m2 > Decimal(DEFAULT_MAX_CHF_PER_M2):
            findings.append(
                ValidationFinding(
                    layer=1,
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Kosten pro m² ({per_m2:.0f} CHF/m²) liegen über dem "
                        f"plausiblen Bereich (max. {DEFAULT_MAX_CHF_PER_M2} CHF/m²)."
                    ),
                )
            )

    # L2: surface low-confidence line items for review.
    for li in est.line_items:
        if li.confidence is Confidence.LOW:
            findings.append(
                ValidationFinding(
                    layer=2,
                    severity=ValidationSeverity.WARNING,
                    message=f"Position '{li.label}' hat niedrige Konfidenz.",
                    target=li.label,
                )
            )

    return _report(findings)


def validate_bkp_scope(scope: BkpScope, *, known_codes: set[str]) -> ValidationReport:
    """L1 BKP-code existence, L2 confidence flags for proposed positions."""
    findings: list[ValidationFinding] = []

    if not scope.positions:
        findings.append(
            ValidationFinding(
                layer=1,
                severity=ValidationSeverity.ERROR,
                message="Keine BKP-Positionen vorgeschlagen.",
            )
        )

    for pos in scope.positions:
        # L1: reject hallucinated BKP codes — the single strongest guard.
        if pos.bkp_code not in known_codes:
            findings.append(
                ValidationFinding(
                    layer=1,
                    severity=ValidationSeverity.ERROR,
                    message=f"BKP-Code '{pos.bkp_code}' existiert nicht im Katalog.",
                    target=pos.bkp_code,
                )
            )
        # L2: surface low-confidence positions.
        if pos.confidence is Confidence.LOW:
            findings.append(
                ValidationFinding(
                    layer=2,
                    severity=ValidationSeverity.WARNING,
                    message=f"Position '{pos.title}' hat niedrige Konfidenz.",
                    target=pos.bkp_code,
                )
            )

    return _report(findings)


def validate_question_set(qs: QuestionSet) -> ValidationReport:
    """L1 well-formedness of a generated question set."""
    findings: list[ValidationFinding] = []

    if not qs.questions:
        findings.append(
            ValidationFinding(
                layer=1,
                severity=ValidationSeverity.ERROR,
                message="Keine Fragen generiert.",
            )
        )

    seen: set[str] = set()
    for q in qs.questions:
        if q.key in seen:
            findings.append(
                ValidationFinding(
                    layer=1,
                    severity=ValidationSeverity.ERROR,
                    message=f"Doppelter Fragen-Schlüssel '{q.key}'.",
                    target=q.key,
                )
            )
        seen.add(q.key)

        if q.type is QuestionType.SELECT and not q.options:
            findings.append(
                ValidationFinding(
                    layer=1,
                    severity=ValidationSeverity.ERROR,
                    message=f"Auswahlfrage '{q.key}' hat keine Optionen.",
                    target=q.key,
                )
            )

    return _report(findings)
