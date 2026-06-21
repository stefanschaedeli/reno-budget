import { useTranslation } from "react-i18next";
import { useBkpBreakdown } from "./api";
import { formatChfRounded, toNumber } from "./format";

interface Props {
  objectId: string;
  year: number | null;
}

/**
 * Horizontal bar chart per top-level eBKP-H group (A/B/C/…). Uses the
 * planned amounts (the actual column is supplementary; rendered as the
 * smaller dark portion for visual comparison).
 */
export function BkpGroupBreakdown({ objectId, year }: Props): JSX.Element {
  const { t } = useTranslation();
  const q = useBkpBreakdown(objectId, year);

  if (q.isLoading) return <p className="text-ink-muted">{t("common.loading")}</p>;
  if (q.isError)
    return <p className="text-negative">{t("budget.errors.generic")}</p>;
  const rows = q.data?.rows ?? [];
  if (rows.length === 0)
    return <p className="text-ink-muted">{t("budget.bkpGroup.empty")}</p>;

  const max = rows.reduce(
    (m, r) => Math.max(m, toNumber(r.planned_chf), toNumber(r.actual_chf)),
    0,
  );
  const safeMax = max === 0 ? 1 : max;

  return (
    <section aria-label={t("budget.bkpGroup.title")} className="space-y-2">
      <h3 className="text-lg font-medium">{t("budget.bkpGroup.title")}</h3>
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-ink-muted">
          <tr>
            <th className="py-1">{t("budget.bkpGroup.group")}</th>
            <th className="py-1">{t("budget.bkpGroup.amount")}</th>
            <th className="py-1 text-right">CHF</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const planned = toNumber(r.planned_chf);
            const widthPct = (planned / safeMax) * 100;
            return (
              <tr key={r.group} data-testid={`bkp-row-${r.group}`}>
                <td className="py-1 font-medium">
                  {r.group === "_uncat"
                    ? t("budget.bkpGroup.uncategorised")
                    : `${r.group} ${r.label}`}
                </td>
                <td className="py-1">
                  <div className="h-3 w-full rounded bg-paper-sunk">
                    <div
                      className="h-3 rounded bg-ink"
                      style={{ width: `${widthPct}%` }}
                      aria-hidden
                    />
                  </div>
                </td>
                <td className="py-1 text-right tabular-nums">
                  {formatChfRounded(r.planned_chf)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
