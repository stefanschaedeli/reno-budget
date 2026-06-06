import { useTranslation } from "react-i18next";
import { useStatusPriorityBreakdown } from "./api";
import { formatChfRounded, toNumber } from "./format";

interface Props {
  objectId: string;
}

const STATUS_ORDER = [
  "idea",
  "planned",
  "in_progress",
  "completed",
  "cancelled",
] as const;
const PRIORITY_ORDER = ["low", "med", "high", "urgent"] as const;

/**
 * Grouped bars: planned amount per (status, priority) tuple. Rendered
 * as a small-multiples grid (one row per status, one cell per priority)
 * to stay readable without a full chart library.
 */
export function StatusPriorityBreakdown({ objectId }: Props): JSX.Element {
  const { t } = useTranslation();
  const q = useStatusPriorityBreakdown(objectId);

  if (q.isLoading) return <p className="text-slate-500">{t("common.loading")}</p>;
  if (q.isError)
    return <p className="text-red-700">{t("budget.errors.generic")}</p>;
  const rows = q.data?.rows ?? [];
  if (rows.length === 0)
    return <p className="text-slate-500">{t("budget.statusPriority.empty")}</p>;

  const max = rows.reduce((m, r) => Math.max(m, toNumber(r.planned_chf)), 0);
  const safeMax = max === 0 ? 1 : max;

  const lookup = new Map<string, number>();
  for (const r of rows) {
    lookup.set(`${r.status}|${r.priority}`, toNumber(r.planned_chf));
  }

  return (
    <section
      aria-label={t("budget.statusPriority.title")}
      className="space-y-2"
    >
      <h3 className="text-lg font-medium">
        {t("budget.statusPriority.title")}
      </h3>
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-slate-500">
          <tr>
            <th className="py-1"> </th>
            {PRIORITY_ORDER.map((p) => (
              <th key={p} className="py-1 text-right">
                {t(`costs.priority.${p}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {STATUS_ORDER.map((s) => (
            <tr key={s}>
              <td className="py-1 font-medium">{t(`costs.status.${s}`)}</td>
              {PRIORITY_ORDER.map((p) => {
                const v = lookup.get(`${s}|${p}`) ?? 0;
                const pct = (v / safeMax) * 100;
                return (
                  <td
                    key={p}
                    className="py-1 pl-2"
                    data-testid={`sp-${s}-${p}`}
                  >
                    <div className="flex items-center gap-1">
                      <div className="h-2 flex-1 rounded bg-slate-100">
                        <div
                          className="h-2 rounded bg-slate-700"
                          style={{ width: `${pct}%` }}
                          aria-hidden
                        />
                      </div>
                      <span className="w-20 text-right text-xs tabular-nums">
                        {formatChfRounded(String(v))}
                      </span>
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
