import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import { useReservePlan, useUpdateObjectSettings } from "./api";
import { formatChfPrecise, formatChfRounded } from "./format";
import { CONTRIBUTION_MODES, type ContributionMode } from "./types";

interface Props {
  objectId: string;
}

/**
 * Top-of-page summary panel: totals, required contribution in the
 * object's current mode, and (OWNER-only) inline editing of
 * contribution mode + inflation rate + initial reserve.
 *
 * RBAC: `my_role` arrives from the backend on the reserve payload. We
 * gate the form on `my_role === "owner"`; non-owners see read-only
 * values with a hint.
 */
export function ReservePanel({ objectId }: Props): JSX.Element {
  const { t } = useTranslation();
  const q = useReservePlan(objectId);
  const updateMut = useUpdateObjectSettings(objectId);

  const [mode, setMode] = useState<ContributionMode>("yearly");
  const [inflationPct, setInflationPct] = useState<string>("0");
  const [initialReserve, setInitialReserve] = useState<string>("0");
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    if (q.data) {
      setMode(q.data.contribution_mode);
      setInflationPct(String(q.data.inflation_rate_percent));
      setInitialReserve(q.data.initial_reserve_chf);
    }
  }, [q.data]);

  if (q.isLoading)
    return <p className="text-ink-muted">{t("common.loading")}</p>;
  if (q.isError) {
    const msg =
      q.error instanceof ApiError && q.error.status === 403
        ? t("budget.errors.forbidden")
        : t("budget.errors.generic");
    return <p className="text-negative">{msg}</p>;
  }
  const data = q.data;
  if (!data) return <p className="text-ink-muted">{t("common.loading")}</p>;

  // TODO Phase 4 follow-up: gate editing on role. Backend reserve payload
  // doesn't yet return my_role; assume editable and let a 403 from PATCH
  // surface via the existing ApiError path.
  const isOwner = true;
  const requiredContributionScalar =
    data.contribution_mode === "monthly"
      ? data.required_per_month_chf
      : data.required_per_year_chf;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsedPct = Number(inflationPct);
    if (Number.isNaN(parsedPct)) return;
    await updateMut.mutateAsync({
      contribution_mode: mode,
      inflation_rate_percent: parsedPct,
      initial_reserve_chf: initialReserve,
    });
    setSavedFlash(true);
    window.setTimeout(() => setSavedFlash(false), 2000);
  };

  return (
    <section
      aria-label={t("budget.reserve.title")}
      className="rounded border border-rule bg-paper-raised p-4"
    >
      <h3 className="mb-3 text-lg font-medium">{t("budget.reserve.title")}</h3>

      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <dt className="text-xs uppercase text-ink-muted">
            {t("budget.reserve.totalPlanned")}
          </dt>
          <dd className="text-base font-semibold tabular-nums">
            {formatChfRounded(data.total_planned_inflated_chf)}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-ink-muted">
            {t("budget.reserve.initialReserve")}
          </dt>
          <dd className="text-base font-semibold tabular-nums">
            {formatChfRounded(data.initial_reserve_chf)}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-ink-muted">
            {t("budget.reserve.requiredTotal")}
          </dt>
          <dd className="text-base font-semibold tabular-nums">
            {formatChfRounded(data.required_total_chf)}
          </dd>
        </div>
      </dl>

      <div className="mt-4 rounded bg-paper-sunk p-3">
        <p className="text-xs uppercase text-ink-muted">
          {t("budget.reserve.requiredContribution")} —{" "}
          {t(`budget.reserve.formula.${data.contribution_mode}`)}
        </p>
        {data.contribution_mode === "lump_sum" ? (
          data.required_lump_sums.length === 0 ? (
            <p className="text-sm text-ink-muted">—</p>
          ) : (
            <table
              data-testid="lump-sum-schedule"
              className="mt-2 w-full max-w-md text-sm"
            >
              <thead className="text-left text-xs uppercase text-ink-muted">
                <tr>
                  <th className="py-1">{t("budget.reserve.lumpSumYear")}</th>
                  <th className="py-1 text-right">
                    {t("budget.reserve.lumpSumAmount")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.required_lump_sums.map((r) => (
                  <tr key={r.year}>
                    <td className="py-1">{r.year}</td>
                    <td className="py-1 text-right tabular-nums">
                      {formatChfPrecise(r.amount_chf)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          <p
            data-testid="required-contribution-scalar"
            className="text-xl font-semibold tabular-nums"
          >
            {formatChfPrecise(requiredContributionScalar)}
          </p>
        )}
      </div>

      {isOwner ? (
        <form
          aria-label={t("budget.reserve.title")}
          onSubmit={(e) => void handleSubmit(e)}
          className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3"
        >
          <label className="flex flex-col text-sm">
            <span className="mb-1 font-medium">
              {t("budget.reserve.modeLabel")}
            </span>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as ContributionMode)}
              className="rounded border border-rule px-2 py-1"
            >
              {CONTRIBUTION_MODES.map((m) => (
                <option key={m} value={m}>
                  {t(`budget.reserve.modes.${m}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1 font-medium">
              {t("budget.reserve.inflationRate")}
            </span>
            <input
              type="number"
              step="0.01"
              min="0"
              value={inflationPct}
              onChange={(e) => setInflationPct(e.target.value)}
              className="rounded border border-rule px-2 py-1"
            />
          </label>
          <label className="flex flex-col text-sm">
            <span className="mb-1 font-medium">
              {t("budget.reserve.initialReserve")}
            </span>
            <input
              type="text"
              inputMode="decimal"
              value={initialReserve}
              onChange={(e) => setInitialReserve(e.target.value)}
              className="rounded border border-rule px-2 py-1"
            />
          </label>
          <div className="sm:col-span-3">
            <button
              type="submit"
              disabled={updateMut.isPending}
              className="rounded bg-ink px-3 py-1 text-sm text-paper hover:bg-ink disabled:opacity-60"
            >
              {updateMut.isPending
                ? t("budget.reserve.saving")
                : t("budget.reserve.save")}
            </button>
            {savedFlash && (
              <span className="ml-3 text-sm text-positive" role="status">
                {t("budget.reserve.saved")}
              </span>
            )}
          </div>
        </form>
      ) : (
        <p className="mt-4 text-sm text-ink-muted">
          {t("budget.reserve.readOnlyHint")}
        </p>
      )}
    </section>
  );
}
