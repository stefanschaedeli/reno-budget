/**
 * Per-object supplier list view (address book).
 *
 * Shows one row per supplier with contact info, archived state, and a
 * create drawer. Archived suppliers are hidden unless the
 * "include archived" toggle is on.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { Drawer } from "@/components/Drawer";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { SupplierForm } from "./SupplierForm";
import { useCreateSupplier, useSuppliers } from "./api";
import type { Supplier, SupplierCreate } from "./types";

export function SuppliersPage(): JSX.Element {
  const { t } = useTranslation();
  const { objectId } = useParams<{ objectId: string }>();
  const [includeArchived, setIncludeArchived] = useState(false);
  const [creating, setCreating] = useState(false);

  const suppliersQuery = useSuppliers(objectId ?? "", { includeArchived });
  const createMut = useCreateSupplier(objectId ?? "");

  if (!objectId) {
    return (
      <PageContainer width="default">
        <p className="text-negative">{t("common.error")}</p>
      </PageContainer>
    );
  }

  const suppliers = suppliersQuery.data ?? [];

  const handleCreate = async (payload: SupplierCreate) => {
    await createMut.mutateAsync(payload);
    setCreating(false);
  };

  return (
    <PageContainer width="default">
      <PageHeader
        title={t("suppliers.title")}
        subtitle={t("suppliers.subtitle")}
        actions={
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded bg-ink px-3 py-1 text-sm text-paper hover:bg-ink"
          >
            {t("suppliers.create")}
          </button>
        }
      />

      <label className="mb-3 inline-flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
        />
        {t("suppliers.includeArchived")}
      </label>

      {suppliersQuery.isLoading && (
        <p className="text-ink-muted">{t("common.loading")}</p>
      )}
      {suppliersQuery.isError && (
        <p className="text-negative">{t("common.error")}</p>
      )}
      {suppliersQuery.isSuccess && suppliers.length === 0 && (
        <p className="text-ink-muted">{t("suppliers.empty")}</p>
      )}
      {suppliers.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-ink-muted">
            <tr className="border-b border-rule">
              <th className="px-2 py-2">{t("suppliers.fields.name")}</th>
              <th className="px-2 py-2">{t("suppliers.fields.email")}</th>
              <th className="px-2 py-2">{t("suppliers.fields.phone")}</th>
              <th className="px-2 py-2">{t("suppliers.fields.archivedAt")}</th>
            </tr>
          </thead>
          <tbody>
            {suppliers.map((s: Supplier) => (
              <tr
                key={s.id}
                data-testid={`supplier-row-${s.id}`}
                className="border-b border-rule hover:bg-paper-sunk"
              >
                <td className="px-2 py-2 font-medium">
                  <Link
                    to={`/lieferanten/${s.id}`}
                    className="hover:underline"
                  >
                    {s.name}
                  </Link>
                </td>
                <td className="px-2 py-2">{s.contact_email ?? "—"}</td>
                <td className="px-2 py-2">{s.contact_phone ?? "—"}</td>
                <td className="px-2 py-2 text-ink-muted">
                  {s.archived_at
                    ? new Date(s.archived_at).toLocaleDateString("de-CH")
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {creating && (
        <Drawer
          title={t("suppliers.create")}
          onClose={() => setCreating(false)}
        >
          <SupplierForm
            onSubmit={handleCreate}
            onCancel={() => setCreating(false)}
            submitting={createMut.isPending}
          />
        </Drawer>
      )}
    </PageContainer>
  );
}
