import { useTranslation } from "react-i18next";
import { useUnitBreakdown } from "./api";
import { formatChfRounded, toNumber } from "./format";

interface Props {
  objectId: string;
}

export function UnitBreakdown({ objectId }: Props): JSX.Element {
  const { t } = useTranslation();
  const q = useUnitBreakdown(objectId);

  if (q.isLoading) return <p className="text-ink-muted">{t("common.loading")}</p>;
  if (q.isError)
    return <p className="text-negative">{t("budget.errors.generic")}</p>;
  const rows = q.data?.rows ?? [];
  if (rows.length === 0)
    return <p className="text-ink-muted">{t("budget.unit.empty")}</p>;

  const max = rows.reduce(
    (m, r) => Math.max(m, toNumber(r.planned_chf)),
    0,
  );
  const safeMax = max === 0 ? 1 : max;

  return (
    <section aria-label={t("budget.unit.title")} className="space-y-2">
      <h3 className="text-lg font-medium">{t("budget.unit.title")}</h3>
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase text-ink-muted">
          <tr>
            <th className="py-1">{t("budget.unit.unit")}</th>
            <th className="py-1">{t("budget.unit.planned")}</th>
            <th className="py-1 text-right">{t("budget.unit.planned")}</th>
            <th className="py-1 text-right">{t("budget.unit.actual")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const planned = toNumber(r.planned_chf);
            const widthPct = (planned / safeMax) * 100;
            return (
              <tr key={r.unit_id} data-testid={`unit-row-${r.unit_id}`}>
                <td className="py-1 font-medium">{r.label}</td>
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
                <td className="py-1 text-right tabular-nums">
                  {formatChfRounded(r.actual_chf)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
