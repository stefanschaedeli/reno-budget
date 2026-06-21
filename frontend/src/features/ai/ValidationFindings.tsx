/**
 * Renders the validation report attached to an artifact — deterministic (L1),
 * grounding (L2), and critic (L3) findings — so the user sees what the system
 * flagged before accepting a draft.
 */
import { useTranslation } from "react-i18next";

import { validationReportSchema, type ValidationFinding } from "./types";

function severityClass(f: ValidationFinding): string {
  if (f.severity === "error") return "text-negative";
  if (f.severity === "warning") return "text-warning";
  return "text-ink-muted";
}

export function ValidationFindings({ raw }: { raw: Record<string, unknown> }) {
  const { t } = useTranslation();
  const parsed = validationReportSchema.safeParse(raw);
  if (!parsed.success) return null;
  const report = parsed.data;

  if (report.findings.length === 0) {
    return <p className="text-xs text-ink-subtle">{t("ai.validation.ok")}</p>;
  }

  return (
    <div className="mt-2">
      <p className="mb-1 text-xs font-medium text-ink-muted">
        {t("ai.validation.heading")}
      </p>
      <ul className="space-y-1">
        {report.findings.map((f, i) => (
          <li key={i} className={`text-xs ${severityClass(f)}`}>
            {f.layer === 3 ? `${t("ai.validation.critic")}: ` : ""}
            {f.message}
          </li>
        ))}
      </ul>
    </div>
  );
}
