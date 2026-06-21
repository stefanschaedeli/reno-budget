import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { formatChf } from "@/features/costs/types";
import { useUpdateProject } from "./api";
import type { Project } from "./types";

const MAX_BAR_PERCENT = 150;

export interface BudgetCardProps {
  project: Project;
  /** Sum of planned_amount_chf across this project's cost items. */
  plannedTotal: number;
  onEstimateSaved?: (() => void) | undefined;
}

function toNumberOrNull(v: string | number | null): number | null {
  if (v === null || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function FieldLabel({ children }: { children: React.ReactNode }): JSX.Element {
  return (
    <p className="mb-1 text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-ink-subtle">
      {children}
    </p>
  );
}

export function BudgetCard({
  project,
  plannedTotal,
  onEstimateSaved,
}: BudgetCardProps): JSX.Element {
  const { t } = useTranslation();
  const estimate = toNumberOrNull(project.rough_estimate_chf);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string>(
    estimate != null ? String(estimate) : "",
  );
  const inputRef = useRef<HTMLInputElement | null>(null);
  const updateMut = useUpdateProject(project.id);

  const diff = estimate != null ? plannedTotal - estimate : null;
  const percent =
    estimate != null && estimate > 0
      ? Math.round((plannedTotal / estimate) * 100)
      : null;
  const over = diff != null && diff > 0;

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
    }
  }, [editing]);

  const openEditor = () => {
    setDraft(estimate != null ? String(estimate) : "");
    setEditing(true);
  };

  const save = async () => {
    try {
      await updateMut.mutateAsync({
        rough_estimate_chf: draft.trim() === "" ? null : draft.trim(),
      });
      setEditing(false);
      onEstimateSaved?.();
    } catch {
      // Keep editor open; error surfaced below via updateMut.isError.
    }
  };

  return (
    <section className="mb-6 border-y border-rule bg-paper py-4">
      <div className="mb-4 flex items-baseline justify-between">
        <h3 className="font-display text-lg font-medium text-ink">
          {t("projects.budget.heading")}
        </h3>
        {percent != null && (
          <span
            className={`font-mono text-xs tabular-nums ${
              percent > 100 ? "text-negative" : "text-ink-muted"
            }`}
          >
            {t("projects.budget.percentOfEstimate", { percent })}
          </span>
        )}
      </div>

      {estimate == null && !editing && (
        <div className="flex items-center justify-between">
          <p className="text-ink-muted">{t("projects.budget.noEstimate")}</p>
          <button
            type="button"
            onClick={openEditor}
            className="rounded-sheet bg-ink px-3 py-1.5 text-sm text-paper transition hover:bg-ink/85"
          >
            {t("projects.budget.addEstimate")}
          </button>
        </div>
      )}

      {(estimate != null || editing) && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <FieldLabel>{t("projects.budget.estimate")}</FieldLabel>
              {editing ? (
                <div className="flex flex-col gap-2">
                  <input
                    id="budget-estimate-input"
                    ref={inputRef}
                    type="number"
                    min={0}
                    step="0.01"
                    inputMode="decimal"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    className="w-40 rounded-sheet border border-rule bg-paper-raised px-2 py-1 font-mono tabular-nums text-ink focus:border-accent focus:outline-none"
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => void save()}
                      disabled={updateMut.isPending}
                      className="rounded-sheet bg-ink px-3 py-1 text-xs text-paper hover:bg-ink/85 disabled:opacity-50"
                    >
                      {t("projects.budget.save")}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(false);
                        setDraft(estimate != null ? String(estimate) : "");
                      }}
                      className="rounded-sheet border border-rule px-3 py-1 text-xs text-ink-muted hover:border-ink/30 hover:text-ink"
                    >
                      {t("projects.budget.cancel")}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-baseline gap-2">
                  <p className="font-mono text-xl font-medium tabular-nums text-ink">
                    {formatChf(String(estimate ?? 0))}
                  </p>
                  <button
                    type="button"
                    onClick={openEditor}
                    className="text-xs text-ink-muted underline-offset-2 hover:text-accent hover:underline"
                  >
                    {t("projects.budget.edit")}
                  </button>
                </div>
              )}
              {editing && updateMut.isError && (
                <p className="mt-1 text-xs text-negative">
                  {(updateMut.error as Error).message}
                </p>
              )}
            </div>

            <div>
              <FieldLabel>{t("projects.budget.planned")}</FieldLabel>
              <p className="font-mono text-xl font-medium tabular-nums text-ink">
                {formatChf(String(plannedTotal))}
              </p>
            </div>

            <div>
              <FieldLabel>{t("projects.budget.diff")}</FieldLabel>
              <p
                data-testid="budget-diff"
                className={
                  "font-mono text-xl font-medium tabular-nums " +
                  (diff == null
                    ? "text-ink-subtle"
                    : over
                      ? "text-negative"
                      : "text-positive")
                }
              >
                {diff == null
                  ? "—"
                  : (over ? "+" : "") + formatChf(String(diff))}
              </p>
            </div>
          </div>

          {estimate != null && estimate > 0 && (
            <div className="mt-4">
              <div className="h-[3px] w-full overflow-hidden bg-paper-sunk">
                <div
                  className={
                    "h-full transition-all " +
                    (percent != null && percent > 100
                      ? "bg-negative"
                      : "bg-positive")
                  }
                  style={{
                    width: `${Math.min(percent ?? 0, MAX_BAR_PERCENT)}%`,
                  }}
                />
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
