/**
 * Renofond projection page (Phase 5).
 *
 * Composed of three blocks:
 *
 *  1. Underfunding banner (red) — only rendered when the backend reports
 *     one or more years with a negative end-of-year balance.
 *  2. Projection chart — a simple SVG bar/line view of the per-year
 *     balance plus the cumulative planned spend. Same visual idiom as
 *     :class:`TimelineChart` so we don't pull in a chart library.
 *  3. Contributions table — read-only for VIEWER/EDITOR, with an
 *     add-form + per-row delete for OWNER.
 *
 * RBAC: ``my_role`` arrives on the contributions list payload; OWNER
 * unlocks mutation affordances. Non-owners see a hint instead of the form.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { apiErrorMessage } from "@/lib/apiError";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { formatChfRounded, toNumber } from "@/features/budget/format";
import {
  useContributions,
  useCreateContribution,
  useDeleteContribution,
  useProjection,
} from "./api";
import type { ProjectionRow } from "./types";

const CHART_HEIGHT = 220;
const VIEW_W = 720;
const LEFT_PAD = 60;
const RIGHT_PAD = 16;
const TOP_PAD = 16;
const BOTTOM_PAD = 32;

const COLOR_BALANCE = "#0E1A2B"; // --ink
const COLOR_NEGATIVE = "#9A2A2A"; // --negative
const COLOR_PLANNED = "#7A8294"; // --ink-subtle

export function RenofondPage(): JSX.Element {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  if (!id)
    return (
      <PageContainer width="wide">
        <p className="text-negative">{t("common.error")}</p>
      </PageContainer>
    );
  return <RenofondPageInner objectId={id} />;
}

function RenofondPageInner({ objectId }: { objectId: string }): JSX.Element {
  const { t } = useTranslation();
  const projection = useProjection(objectId);
  const contributions = useContributions(objectId);

  if (projection.isLoading || contributions.isLoading) {
    return (
      <PageContainer width="wide">
        <p className="text-ink-muted">{t("common.loading")}</p>
      </PageContainer>
    );
  }
  if (projection.isError) {
    const msg =
      projection.error instanceof ApiError && projection.error.status === 403
        ? t("renofond.errors.forbidden")
        : t("renofond.errors.generic");
    return (
      <PageContainer width="wide">
        <p className="text-negative">{msg}</p>
      </PageContainer>
    );
  }
  if (contributions.isError) {
    return (
      <PageContainer width="wide">
        <p className="text-negative">{t("renofond.errors.generic")}</p>
      </PageContainer>
    );
  }
  const proj = projection.data!;
  const contribs = contributions.data!;
  const isOwner = contribs.my_role === "owner";

  return (
    <PageContainer width="wide">
      <PageHeader title={t("renofond.title")} subtitle={t("renofond.subtitle")} />
      <div className="space-y-6">

      {proj.underfunding_years.length > 0 && (
        <div
          role="alert"
          data-testid="underfunding-banner"
          className="rounded border border-negative bg-negative-soft p-4 text-negative"
        >
          <p className="font-medium">{t("renofond.underfunding.banner")}</p>
          <ul className="mt-2 list-inside list-disc text-sm">
            {proj.underfunding_years.map((u) => (
              <li key={u.year}>
                {u.year}: {formatChfRounded(u.shortfall_chf)}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="rounded border border-rule bg-paper-raised p-4">
        <ProjectionChart rows={proj.rows} />
      </div>

      <div className="rounded border border-rule bg-paper-raised p-4">
        <h3 className="mb-3 text-lg font-medium">
          {t("renofond.contributions.title")}
        </h3>
        <ContributionsTable
          objectId={objectId}
          rows={contribs.items}
          isOwner={isOwner}
        />
        {isOwner ? (
          <AddContributionForm objectId={objectId} />
        ) : (
          <p className="mt-4 text-sm text-ink-muted">
            {t("renofond.contributions.readOnlyHint")}
          </p>
        )}
      </div>
      </div>
    </PageContainer>
  );
}

function ProjectionChart({ rows }: { rows: ProjectionRow[] }): JSX.Element {
  const { t } = useTranslation();
  if (rows.length === 0) {
    return (
      <p className="text-ink-muted">{t("renofond.projection.noData")}</p>
    );
  }
  const balances = rows.map((r) => toNumber(r.balance_chf));
  const cumulative = rows.map((r) => toNumber(r.cumulative_planned_chf));
  const maxVal = Math.max(1, ...balances, ...cumulative);
  const minVal = Math.min(0, ...balances);
  const range = maxVal - minVal || 1;

  const chartW = VIEW_W - LEFT_PAD - RIGHT_PAD;
  const usableH = CHART_HEIGHT - TOP_PAD - BOTTOM_PAD;
  const slotW = chartW / rows.length;
  const barW = Math.max(4, slotW * 0.6);
  const zeroY = TOP_PAD + (maxVal / range) * usableH;

  return (
    <section
      aria-label={t("renofond.projection.title")}
      data-testid="projection-chart"
      className="space-y-3"
    >
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-medium">{t("renofond.projection.title")}</h3>
        <div className="flex items-center gap-4 text-xs text-ink-muted">
          <span className="flex items-center gap-1">
            <span
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: COLOR_BALANCE }}
            />
            {t("renofond.projection.legendBalance")}
          </span>
          <span className="flex items-center gap-1">
            <span
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: COLOR_PLANNED }}
            />
            {t("renofond.projection.legendPlanned")}
          </span>
        </div>
      </header>

      <svg
        role="img"
        aria-label={t("renofond.projection.title")}
        viewBox={`0 0 ${VIEW_W} ${CHART_HEIGHT}`}
        className="w-full border border-rule bg-paper-raised"
      >
        <line
          x1={LEFT_PAD}
          y1={zeroY}
          x2={VIEW_W - RIGHT_PAD}
          y2={zeroY}
          stroke="#e2e8f0"
        />
        {rows.map((row, i) => {
          const balance = toNumber(row.balance_chf);
          const planned = toNumber(row.cumulative_planned_chf);
          const x0 = LEFT_PAD + i * slotW + (slotW - barW) / 2;
          const balanceH = (Math.abs(balance) / range) * usableH;
          const plannedH = (planned / range) * usableH;
          const balanceY = balance >= 0 ? zeroY - balanceH : zeroY;
          const plannedY = zeroY - plannedH;
          return (
            <g
              key={row.year}
              data-testid={`projection-year-${row.year}`}
              data-balance={balance}
              data-planned={planned}
            >
              <title>
                {row.year}: {t("renofond.projection.balance")}{" "}
                {formatChfRounded(row.balance_chf)} ·{" "}
                {t("renofond.projection.cumulative")}{" "}
                {formatChfRounded(row.cumulative_planned_chf)}
              </title>
              <rect
                x={x0}
                y={plannedY}
                width={barW}
                height={plannedH}
                fill={COLOR_PLANNED}
                opacity={0.35}
              />
              <rect
                x={x0}
                y={balanceY}
                width={barW}
                height={balanceH}
                fill={row.is_underfunded ? COLOR_NEGATIVE : COLOR_BALANCE}
              />
              <text
                x={x0 + barW / 2}
                y={CHART_HEIGHT - 12}
                textAnchor="middle"
                fontSize={10}
                fill="#475569"
              >
                {row.year}
              </text>
            </g>
          );
        })}
      </svg>
    </section>
  );
}

function ContributionsTable({
  objectId,
  rows,
  isOwner,
}: {
  objectId: string;
  rows: { id: string; year: number; amount_chf: string; note: string | null; created_at: string }[];
  isOwner: boolean;
}): JSX.Element {
  const { t } = useTranslation();
  const deleteMut = useDeleteContribution(objectId);
  if (rows.length === 0) {
    return (
      <p
        data-testid="contributions-empty"
        className="text-sm text-ink-muted"
      >
        {t("renofond.contributions.empty")}
      </p>
    );
  }
  return (
    <table className="w-full text-sm" data-testid="contributions-table">
      <thead className="border-b border-rule text-left text-xs uppercase text-ink-muted">
        <tr>
          <th className="py-1">{t("renofond.contributions.year")}</th>
          <th className="py-1 text-right">
            {t("renofond.contributions.amount")}
          </th>
          <th className="py-1">{t("renofond.contributions.note")}</th>
          {isOwner && (
            <th className="py-1 text-right">
              {t("renofond.contributions.actions")}
            </th>
          )}
        </tr>
      </thead>
      <tbody className="divide-y divide-rule">
        {rows.map((c) => (
          <tr key={c.id}>
            <td className="py-1">{c.year}</td>
            <td className="py-1 text-right tabular-nums">
              {formatChfRounded(c.amount_chf)}
            </td>
            <td className="py-1 text-ink-muted">{c.note ?? ""}</td>
            {isOwner && (
              <td className="py-1 text-right">
                <button
                  type="button"
                  onClick={() => deleteMut.mutate(c.id)}
                  className="text-xs text-negative hover:underline"
                >
                  {t("renofond.contributions.delete")}
                </button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AddContributionForm({
  objectId,
}: {
  objectId: string;
}): JSX.Element {
  const { t } = useTranslation();
  const createMut = useCreateContribution(objectId);
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState<string>(String(currentYear));
  const [amount, setAmount] = useState<string>("");
  const [note, setNote] = useState<string>("");
  const [savedFlash, setSavedFlash] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const yNum = Number(year);
    if (!Number.isInteger(yNum) || yNum < 1900 || yNum > 2200) {
      setError(t("renofond.errors.invalidYear"));
      return;
    }
    if (amount === "" || Number.isNaN(Number(amount)) || Number(amount) < 0) {
      setError(t("renofond.errors.invalidAmount"));
      return;
    }
    try {
      await createMut.mutateAsync({
        year: yNum,
        amount_chf: amount,
        note: note || null,
      });
      setAmount("");
      setNote("");
      setSavedFlash(true);
      window.setTimeout(() => setSavedFlash(false), 2000);
    } catch (err) {
      setError(
        apiErrorMessage(err, t("renofond.errors.generic")),
      );
    }
  };

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      aria-label={t("renofond.contributions.add")}
      className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-4"
    >
      <label className="flex flex-col text-sm">
        <span className="mb-1 font-medium">
          {t("renofond.contributions.year")}
        </span>
        <input
          type="number"
          value={year}
          onChange={(e) => setYear(e.target.value)}
          className="rounded border border-rule px-2 py-1"
        />
      </label>
      <label className="flex flex-col text-sm">
        <span className="mb-1 font-medium">
          {t("renofond.contributions.amount")}
        </span>
        <input
          type="text"
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="rounded border border-rule px-2 py-1"
        />
      </label>
      <label className="flex flex-col text-sm sm:col-span-2">
        <span className="mb-1 font-medium">
          {t("renofond.contributions.note")}
        </span>
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="rounded border border-rule px-2 py-1"
        />
      </label>
      <div className="sm:col-span-4">
        <button
          type="submit"
          disabled={createMut.isPending}
          className="rounded bg-ink px-3 py-1 text-sm text-paper hover:bg-ink disabled:opacity-60"
        >
          {createMut.isPending
            ? t("renofond.contributions.submitting")
            : t("renofond.contributions.submit")}
        </button>
        {savedFlash && (
          <span className="ml-3 text-sm text-positive" role="status">
            {t("renofond.contributions.saved")}
          </span>
        )}
        {error && (
          <span className="ml-3 text-sm text-negative" role="alert">
            {error}
          </span>
        )}
      </div>
    </form>
  );
}
