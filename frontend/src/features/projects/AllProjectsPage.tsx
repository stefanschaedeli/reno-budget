/**
 * Cross-object project list.
 *
 * One row per non-archived project across every object the current user
 * can access. Each row links to the project's detail page and to its
 * parent object. Mirrors the FinancesPage cross-object pattern.
 */
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { formatChf } from "@/features/costs/types";
import { useAllProjects } from "./api";
import type { ProjectListItem } from "./types";

export function AllProjectsPage(): JSX.Element {
  const { t } = useTranslation();
  const q = useAllProjects();

  return (
    <PageContainer width="default">
      <PageHeader
        title={t("projects.allTitle")}
        subtitle={t("projects.allSubtitle")}
      />

      <p className="mb-4 text-sm text-slate-500">
        {t("projects.createHint")}{" "}
        <Link to="/objekte" className="underline hover:text-slate-900">
          {t("nav.objects")}
        </Link>
      </p>

      {q.isLoading && <p className="text-slate-500">{t("common.loading")}</p>}
      {q.isError && <p className="text-red-700">{t("common.error")}</p>}
      {q.isSuccess && q.data.length === 0 && (
        <p className="text-slate-500">{t("projects.empty")}</p>
      )}
      {q.isSuccess && q.data.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
              <th className="px-2 py-2">{t("projects.fields.name")}</th>
              <th className="px-2 py-2">{t("projects.fields.object")}</th>
              <th className="px-2 py-2">{t("projects.fields.status")}</th>
              <th className="px-2 py-2 text-right">
                {t("projects.fields.roughEstimate")}
              </th>
              <th className="px-2 py-2">{t("projects.fields.plannedYear")}</th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((p: ProjectListItem) => (
              <tr
                key={p.id}
                data-testid={`all-project-row-${p.id}`}
                className="border-b border-slate-200 hover:bg-slate-50"
              >
                <td className="px-2 py-2 font-medium">
                  <Link to={`/projekte/${p.id}`} className="hover:underline">
                    {p.name}
                  </Link>
                </td>
                <td className="px-2 py-2">
                  <Link
                    to={`/objekte/${p.object_id}`}
                    className="text-slate-600 underline-offset-2 hover:underline"
                  >
                    {p.object_name}
                  </Link>
                </td>
                <td className="px-2 py-2">
                  {t(`projects.status.${p.status}`)}
                </td>
                <td className="px-2 py-2 text-right tabular-nums">
                  {p.rough_estimate_chf != null
                    ? formatChf(String(p.rough_estimate_chf))
                    : "—"}
                </td>
                <td className="px-2 py-2">{p.planned_year ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </PageContainer>
  );
}
