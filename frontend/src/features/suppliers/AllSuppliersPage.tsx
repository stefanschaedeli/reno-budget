/**
 * Cross-object supplier list.
 */
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { useAllSuppliers } from "./api";
import type { SupplierListItem } from "./types";

export function AllSuppliersPage(): JSX.Element {
  const { t } = useTranslation();
  const q = useAllSuppliers();

  return (
    <PageContainer width="default">
      <PageHeader
        title={t("suppliers.allTitle")}
        subtitle={t("suppliers.allSubtitle")}
      />

      {q.isLoading && <p className="text-slate-500">{t("common.loading")}</p>}
      {q.isError && <p className="text-red-700">{t("common.error")}</p>}
      {q.isSuccess && q.data.length === 0 && (
        <p className="text-slate-500">{t("suppliers.empty")}</p>
      )}
      {q.isSuccess && q.data.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
              <th className="px-2 py-2">{t("suppliers.fields.name")}</th>
              <th className="px-2 py-2">{t("suppliers.fields.object")}</th>
              <th className="px-2 py-2">{t("suppliers.fields.email")}</th>
              <th className="px-2 py-2">{t("suppliers.fields.phone")}</th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((s: SupplierListItem) => (
              <tr
                key={s.id}
                data-testid={`all-supplier-row-${s.id}`}
                className="border-b border-slate-200 hover:bg-slate-50"
              >
                <td className="px-2 py-2 font-medium">
                  <Link to={`/lieferanten/${s.id}`} className="hover:underline">
                    {s.name}
                  </Link>
                </td>
                <td className="px-2 py-2">
                  <Link
                    to={`/objekte/${s.object_id}`}
                    className="text-slate-600 underline-offset-2 hover:underline"
                  >
                    {s.object_name}
                  </Link>
                </td>
                <td className="px-2 py-2">{s.contact_email ?? "—"}</td>
                <td className="px-2 py-2">{s.contact_phone ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </PageContainer>
  );
}
