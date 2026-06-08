import { useState } from "react";
import { useTranslation } from "react-i18next";
import { formatChf } from "@/features/costs/types";
import { useUpdateProject } from "./api";
import type { Project } from "./types";

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
  const updateMut = useUpdateProject(project.id);

  const diff = estimate != null ? plannedTotal - estimate : null;
  const percent =
    estimate != null && estimate > 0
      ? Math.round((plannedTotal / estimate) * 100)
      : null;
  const over = diff != null && diff > 0;

  const save = async () => {
    await updateMut.mutateAsync({
      rough_estimate_chf: draft.trim() === "" ? null : draft.trim(),
    });
    setEditing(false);
    onEstimateSaved?.();
  };

  return (
    <section className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
        {t("projects.budget.heading")}
      </h3>

      {estimate == null && !editing && (
        <div className="flex items-center justify-between">
          <p className="text-slate-500">{t("projects.budget.noEstimate")}</p>
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
          >
            {t("projects.budget.addEstimate")}
          </button>
        </div>
      )}

      {(estimate != null || editing) && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-slate-500">
                {t("projects.budget.estimate")}
              </p>
              {editing ? (
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    inputMode="decimal"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    className="w-32 rounded border border-slate-300 px-2 py-1 tabular-nums"
                  />
                  <button
                    type="button"
                    onClick={() => void save()}
                    disabled={updateMut.isPending}
                    className="rounded bg-slate-900 px-2 py-1 text-xs text-white hover:bg-slate-700 disabled:opacity-50"
                  >
                    {t("projects.budget.save")}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(false);
                      setDraft(estimate != null ? String(estimate) : "");
                    }}
                    className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100"
                  >
                    {t("projects.budget.cancel")}
                  </button>
                </div>
              ) : (
                <div className="flex items-baseline gap-2">
                  <p className="text-2xl font-semibold tabular-nums">
                    {formatChf(String(estimate ?? 0))}
                  </p>
                  <button
                    type="button"
                    onClick={() => setEditing(true)}
                    className="text-xs text-slate-500 hover:text-slate-900"
                  >
                    {t("projects.budget.edit")}
                  </button>
                </div>
              )}
            </div>

            <div>
              <p className="text-xs text-slate-500">
                {t("projects.budget.planned")}
              </p>
              <p className="text-2xl font-semibold tabular-nums">
                {formatChf(String(plannedTotal))}
              </p>
            </div>

            <div>
              <p className="text-xs text-slate-500">
                {t("projects.budget.diff")}
              </p>
              <p
                data-testid="budget-diff"
                className={
                  "text-2xl font-semibold tabular-nums " +
                  (diff == null
                    ? "text-slate-400"
                    : over
                      ? "text-red-700"
                      : "text-emerald-700")
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
              <div className="h-2 w-full overflow-hidden rounded bg-slate-100">
                <div
                  className={
                    "h-full " +
                    (percent != null && percent > 100
                      ? "bg-red-500"
                      : "bg-emerald-500")
                  }
                  style={{
                    width: `${Math.min(percent ?? 0, 150)}%`,
                  }}
                />
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {t("projects.budget.percentOfEstimate", { percent })}
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
