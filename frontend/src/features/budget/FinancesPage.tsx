import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useFinancesOverview } from "./api";
import { formatChfRounded, toNumber } from "./format";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";

/**
 * Cross-object roll-up. One row per object visible to the user, sorted
 * by required-per-year DESC so the most pressing reserves bubble up.
 * Rows show a "anteilig" badge when the user has scoped membership and
 * the figures are pro-rated.
 */
export function FinancesPage(): JSX.Element {
  const { t } = useTranslation();
  const q = useFinancesOverview();

  const sortedRows = useMemo(() => {
    const rows = q.data?.rows ?? [];
    return [...rows].sort(
      (a, b) =>
        toNumber(b.required_per_year_chf) - toNumber(a.required_per_year_chf),
    );
  }, [q.data]);

  return (
    <PageContainer width="default">
      <PageHeader
        title={t("budget.finances.title")}
        subtitle={t("budget.finances.subtitle")}
      />
      <div className="space-y-4">

      {q.isLoading && <p className="text-ink-muted">{t("common.loading")}</p>}
      {q.isError && (
        <p className="text-negative">{t("budget.errors.generic")}</p>
      )}
      {q.data && sortedRows.length === 0 && (
        <p className="text-ink-muted">{t("budget.finances.empty")}</p>
      )}
      {q.data && sortedRows.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-ink-muted">
            <tr>
              <th className="py-2">{t("budget.finances.object")}</th>
              <th className="py-2">{t("budget.finances.role")}</th>
              <th className="py-2 text-right">
                {t("budget.finances.plannedTotal")}
              </th>
              <th className="py-2 text-right">
                {t("budget.finances.actualTotal")}
              </th>
              <th className="py-2 text-right">
                {t("budget.finances.requiredPerYear")}
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((r) => (
              <tr
                key={r.object_id}
                data-testid={`finances-row-${r.object_id}`}
                className="border-t border-rule"
              >
                <td className="py-2">
                  <Link
                    to={`/objekte/${r.object_id}/budget`}
                    className="font-medium text-ink underline-offset-2 hover:underline"
                  >
                    {r.name}
                  </Link>
                  {r.is_scoped && (
                    <span
                      data-testid={`scoped-badge-${r.object_id}`}
                      className="ml-2 rounded bg-warning-soft px-1.5 py-0.5 text-xs text-warning"
                    >
                      {t("budget.finances.scopedBadge")}
                    </span>
                  )}
                </td>
                <td className="py-2">
                  {t(`budget.finances.roles.${r.role}`)}
                </td>
                <td className="py-2 text-right tabular-nums">
                  {formatChfRounded(r.total_planned_inflated_chf)}
                </td>
                <td className="py-2 text-right tabular-nums">
                  {formatChfRounded(r.total_actual_chf)}
                </td>
                <td className="py-2 text-right font-medium tabular-nums">
                  {formatChfRounded(r.required_per_year_chf)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      </div>
    </PageContainer>
  );
}
