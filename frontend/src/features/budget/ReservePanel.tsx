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
    return <p className="text-slate-500">{t("common.loading")}</p>;
  if (q.isError) {
    const msg =
      q.error instanceof ApiError && q.error.status === 403
        ? t("budget.errors.forbidden")
        : t("budget.errors.generic");
    return <p className="text-red-700">{msg}</p>;
  }
  const data = q.data;
  if (!data) return <p className="text-slate-500">{t("common.loading")}</p>;

  const isOwner = data.my_role === "owner";

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
      className="rounded border border-slate-200 bg-white p-4"
    >
      <h3 className="mb-3 text-lg font-medium">{t("budget.reserve.title")}</h3>

      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <dt className="text-xs uppercase text-slate-500">
            {t("budget.reserve.totalPlanned")}
          </dt>
          <dd className="text-base font-semibold tabular-nums">
            {formatChfRounded(data.total_planned_inflated_chf)}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-slate-500">
            {t("budget.reserve.initialReserve")}
          </dt>
          <dd className="text-base font-semibold tabular-nums">
            {formatChfRounded(data.initial_reserve_chf)}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-slate-500">
            {t("budget.reserve.requiredTotal")}
          </dt>
          <dd className="text-base font-semibold tabular-nums">
            {formatChfRounded(data.required_total_chf)}
          </dd>
        </div>
      </dl>

      <div className="mt-4 rounded bg-slate-50 p-3">
        <p className="text-xs uppercase text-slate-500">
          {t("budget.reserve.requiredContribution")} —{" "}
          {t(`budget.reserve.formula.${data.contribution_mode}`)}
        </p>
        {data.contribution_mode === "lump_sum" ? (
          data.lump_sum_schedule.length === 0 ? (
            <p className="text-sm text-slate-500">—</p>
          ) : (
            <table
              data-testid="lump-sum-schedule"
              className="mt-2 w-full max-w-md text-sm"
            >
              <thead className="text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-1">{t("budget.reserve.lumpSumYear")}</th>
                  <th className="py-1 text-right">
                    {t("budget.reserve.lumpSumAmount")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.lump_sum_schedule.map((r) => (
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
            {formatChfPrecise(data.required_contribution_chf)}
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
              className="rounded border border-slate-300 px-2 py-1"
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
              className="rounded border border-slate-300 px-2 py-1"
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
              className="rounded border border-slate-300 px-2 py-1"
            />
          </label>
          <div className="sm:col-span-3">
            <button
              type="submit"
              disabled={updateMut.isPending}
              className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700 disabled:opacity-60"
            >
              {updateMut.isPending
                ? t("budget.reserve.saving")
                : t("budget.reserve.save")}
            </button>
            {savedFlash && (
              <span className="ml-3 text-sm text-green-700" role="status">
                {t("budget.reserve.saved")}
              </span>
            )}
          </div>
        </form>
      ) : (
        <p className="mt-4 text-sm text-slate-500">
          {t("budget.reserve.readOnlyHint")}
        </p>
      )}
    </section>
  );
}
