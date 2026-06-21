/**
 * Renders one AI-generated, typed question as a real form input and validates
 * the answer against the question's own constraints (min/max for numbers,
 * required-ness). The AI chooses *which* questions to ask; this component
 * guarantees a typed, validated answer regardless.
 */
import { useTranslation } from "react-i18next";

import type { GeneratedQuestion } from "./types";

export type AnswerValue = string | number | boolean | null;

interface QuestionFieldProps {
  question: GeneratedQuestion;
  value: AnswerValue;
  onChange: (value: AnswerValue) => void;
}

const inputClass =
  "w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none";

/** Returns a German validation message, or null if the answer is acceptable. */
export function validateAnswer(
  q: GeneratedQuestion,
  value: AnswerValue,
): string | null {
  const empty = value === null || value === "" || value === undefined;
  if (q.required && empty && q.type !== "boolean") {
    return "Pflichtfeld";
  }
  if (q.type === "number" && !empty) {
    const n = Number(value);
    if (Number.isNaN(n)) return "Bitte eine Zahl eingeben";
    if (q.min != null && n < q.min) return `Mindestens ${q.min}`;
    if (q.max != null && n > q.max) return `Höchstens ${q.max}`;
  }
  return null;
}

export function QuestionField({ question, value, onChange }: QuestionFieldProps) {
  const { t } = useTranslation();
  const error = validateAnswer(question, value);

  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-ink">
        {question.label}
        {question.unit ? ` (${question.unit})` : ""}
      </span>

      {question.type === "number" && (
        <input
          type="number"
          inputMode="decimal"
          value={value === null || value === undefined ? "" : String(value)}
          min={question.min ?? undefined}
          max={question.max ?? undefined}
          onChange={(e) =>
            onChange(e.target.value === "" ? null : Number(e.target.value))
          }
          className={`${inputClass} font-mono tabular-nums`}
          aria-label={question.label}
        />
      )}

      {question.type === "text" && (
        <input
          type="text"
          value={value === null || value === undefined ? "" : String(value)}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
          aria-label={question.label}
        />
      )}

      {question.type === "select" && (
        <select
          value={value === null || value === undefined ? "" : String(value)}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
          aria-label={question.label}
        >
          <option value="">{t("ai.question.choose")}</option>
          {(question.options ?? []).map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      )}

      {question.type === "boolean" && (
        <span className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={value === true}
            onChange={(e) => onChange(e.target.checked)}
            aria-label={question.label}
          />
          <span className="text-ink-muted">{t("ai.question.yes")}</span>
        </span>
      )}

      {question.help && (
        <span className="mt-1 block text-xs text-ink-subtle">{question.help}</span>
      )}
      {error && <span className="mt-1 block text-xs text-negative">{error}</span>}
    </label>
  );
}
