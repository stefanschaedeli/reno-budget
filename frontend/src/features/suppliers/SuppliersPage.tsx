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
      <p className="mx-auto mt-12 max-w-5xl p-6 text-red-700">
        {t("common.error")}
      </p>
    );
  }

  const suppliers = suppliersQuery.data ?? [];

  const handleCreate = async (payload: SupplierCreate) => {
    await createMut.mutateAsync(payload);
    setCreating(false);
  };

  return (
    <section className="mx-auto mt-8 max-w-5xl p-6">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">{t("suppliers.title")}</h2>
          <p className="text-slate-500">{t("suppliers.subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
        >
          {t("suppliers.create")}
        </button>
      </header>

      <label className="mb-3 inline-flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
        />
        {t("suppliers.includeArchived")}
      </label>

      {suppliersQuery.isLoading && (
        <p className="text-slate-500">{t("common.loading")}</p>
      )}
      {suppliersQuery.isError && (
        <p className="text-red-700">{t("common.error")}</p>
      )}
      {suppliersQuery.isSuccess && suppliers.length === 0 && (
        <p className="text-slate-500">{t("suppliers.empty")}</p>
      )}
      {suppliers.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
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
                className="border-b border-slate-200 hover:bg-slate-50"
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
                <td className="px-2 py-2 text-slate-500">
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
    </section>
  );
}

interface DrawerProps {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

function Drawer({ title, onClose, children }: DrawerProps): JSX.Element {
  return (
    <div className="fixed inset-0 z-40 flex">
      <div
        className="flex-1 bg-slate-900/40"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside className="z-50 w-full max-w-xl overflow-y-auto bg-white p-6 shadow-xl">
        <header className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Schliessen"
            className="text-slate-500 hover:text-slate-900"
          >
            ×
          </button>
        </header>
        {children}
      </aside>
    </div>
  );
}
