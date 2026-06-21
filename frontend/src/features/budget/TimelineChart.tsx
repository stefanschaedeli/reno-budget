import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "@/api/client";
import { useBudgetTimeline } from "./api";
import { formatChfRounded, toNumber } from "./format";

interface TimelineChartProps {
  objectId: string;
}

const CHART_HEIGHT = 240;
const BAR_GAP = 6;
const LEFT_PAD = 60;
const RIGHT_PAD = 16;
const TOP_PAD = 16;
const BOTTOM_PAD = 32;
const VIEW_W = 720;

const COLOR_PLANNED = "#7A8294"; // --ink-subtle
const COLOR_ACTUAL = "#0E1A2B"; // --ink

/**
 * Stacked / grouped bar chart by year. Two series: planned (nominal or
 * inflated, toggled by the user) and actual. Clicking a year opens a
 * side panel listing the cost items in that year.
 */
export function TimelineChart({ objectId }: TimelineChartProps): JSX.Element {
  const { t } = useTranslation();
  const [inflated, setInflated] = useState(true);
  const q = useBudgetTimeline(objectId, { inflated });

  if (q.isLoading) return <p className="text-ink-muted">{t("common.loading")}</p>;
  if (q.isError) {
    const msg =
      q.error instanceof ApiError && q.error.status === 403
        ? t("budget.errors.forbidden")
        : t("budget.errors.generic");
    return <p className="text-negative">{msg}</p>;
  }
  const data = q.data;
  if (!data || data.rows.length === 0) {
    return <p className="text-ink-muted">{t("budget.timeline.noData")}</p>;
  }

  const rows = data.rows;
  const plannedField: "planned_inflated_chf" | "planned_chf" = inflated
    ? "planned_inflated_chf"
    : "planned_chf";
  const maxVal = rows.reduce((m, r) => {
    const v = Math.max(toNumber(r[plannedField]), toNumber(r.actual_chf));
    return v > m ? v : m;
  }, 0);
  const safeMax = maxVal === 0 ? 1 : maxVal;

  const chartW = VIEW_W - LEFT_PAD - RIGHT_PAD;
  const usableH = CHART_HEIGHT - TOP_PAD - BOTTOM_PAD;
  const slotW = chartW / rows.length;
  const barW = (slotW - BAR_GAP) / 2;

  return (
    <section aria-label={t("budget.timeline.title")} className="space-y-3">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-lg font-medium">{t("budget.timeline.title")}</h3>
        <fieldset className="flex items-center gap-2 text-sm">
          <legend className="sr-only">{t("budget.inflationToggle.label")}</legend>
          <label className="flex items-center gap-1">
            <input
              type="radio"
              name="inflation"
              value="nominal"
              checked={!inflated}
              onChange={() => setInflated(false)}
            />
            {t("budget.inflationToggle.nominal")}
          </label>
          <label className="flex items-center gap-1">
            <input
              type="radio"
              name="inflation"
              value="inflated"
              checked={inflated}
              onChange={() => setInflated(true)}
            />
            {t("budget.inflationToggle.inflated")}
          </label>
        </fieldset>
      </header>

      <div className="flex items-center gap-4 text-xs text-ink-muted">
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: COLOR_PLANNED }}
          />
          {t("budget.timeline.planned")}
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: COLOR_ACTUAL }}
          />
          {t("budget.timeline.actual")}
        </span>
      </div>

      <svg
        role="img"
        aria-label={t("budget.timeline.title")}
        viewBox={`0 0 ${VIEW_W} ${CHART_HEIGHT}`}
        className="w-full border border-rule bg-paper-raised"
      >
        <line
          x1={LEFT_PAD}
          y1={TOP_PAD + usableH}
          x2={VIEW_W - RIGHT_PAD}
          y2={TOP_PAD + usableH}
          stroke="#e2e8f0"
        />
        <text
          x={LEFT_PAD - 8}
          y={TOP_PAD + 10}
          textAnchor="end"
          fontSize={10}
          fill="#64748b"
        >
          {formatChfRounded(String(safeMax))}
        </text>
        <text
          x={LEFT_PAD - 8}
          y={TOP_PAD + usableH}
          textAnchor="end"
          fontSize={10}
          fill="#64748b"
        >
          0
        </text>

        {rows.map((row, i) => {
          const plannedVal = toNumber(row[plannedField]);
          const actualVal = toNumber(row.actual_chf);
          const plannedH = (plannedVal / safeMax) * usableH;
          const actualH = (actualVal / safeMax) * usableH;
          const x0 = LEFT_PAD + i * slotW + BAR_GAP / 2;
          const yBase = TOP_PAD + usableH;
          return (
            <g
              key={row.year}
              data-testid={`timeline-year-${row.year}`}
              data-planned={plannedVal}
              data-actual={actualVal}
            >
              <title>
                {row.year}: {t("budget.timeline.planned")}{" "}
                {formatChfRounded(row[plannedField])} ·{" "}
                {t("budget.timeline.actual")} {formatChfRounded(row.actual_chf)}
              </title>
              <rect
                x={x0}
                y={yBase - plannedH}
                width={barW}
                height={plannedH}
                fill={COLOR_PLANNED}
              />
              <rect
                x={x0 + barW}
                y={yBase - actualH}
                width={barW}
                height={actualH}
                fill={COLOR_ACTUAL}
              />
              <text
                x={x0 + barW}
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
