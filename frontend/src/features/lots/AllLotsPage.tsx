/**
 * Cross-object lot list.
 */
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { useAllLots } from "./api";
import type { LotListItem } from "./types";

export function AllLotsPage(): JSX.Element {
  const { t } = useTranslation();
  const q = useAllLots();

  return (
    <PageContainer width="default">
      <PageHeader title={t("lots.allTitle")} subtitle={t("lots.allSubtitle")} />

      {q.isLoading && <p className="text-slate-500">{t("common.loading")}</p>}
      {q.isError && <p className="text-red-700">{t("common.error")}</p>}
      {q.isSuccess && q.data.length === 0 && (
        <p className="text-slate-500">{t("lots.empty")}</p>
      )}
      {q.isSuccess && q.data.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
              <th className="px-2 py-2">{t("lots.fields.name")}</th>
              <th className="px-2 py-2">{t("lots.fields.object")}</th>
              <th className="px-2 py-2">{t("lots.fields.status")}</th>
              <th className="px-2 py-2">{t("lots.fields.tenderDeadline")}</th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((l: LotListItem) => (
              <tr
                key={l.id}
                data-testid={`all-lot-row-${l.id}`}
                className="border-b border-slate-200 hover:bg-slate-50"
              >
                <td className="px-2 py-2 font-medium">
                  <Link to={`/lose/${l.id}`} className="hover:underline">
                    {l.name}
                  </Link>
                </td>
                <td className="px-2 py-2">
                  <Link
                    to={`/objekte/${l.object_id}`}
                    className="text-slate-600 underline-offset-2 hover:underline"
                  >
                    {l.object_name}
                  </Link>
                </td>
                <td className="px-2 py-2">{t(`lots.status.${l.status}`)}</td>
                <td className="px-2 py-2">
                  {l.tender_deadline
                    ? new Date(l.tender_deadline).toLocaleDateString("de-CH")
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </PageContainer>
  );
}
