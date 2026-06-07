/**
 * Supplier detail / edit page.
 *
 * Shows supplier contact info, an edit form, archive + delete buttons.
 * Deletion is blocked by the API (409) if any quote references the
 * supplier — we surface the German error message directly.
 */
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { SupplierForm } from "./SupplierForm";
import {
  useArchiveSupplier,
  useDeleteSupplier,
  useSupplier,
  useUpdateSupplier,
} from "./api";
import type { SupplierCreate } from "./types";

export function SupplierDetailPage(): JSX.Element {
  const { t } = useTranslation();
  const { supplierId } = useParams<{ supplierId: string }>();
  const navigate = useNavigate();

  const supplierQuery = useSupplier(supplierId ?? "");
  const updateMut = useUpdateSupplier(supplierId ?? "");
  const archiveMut = useArchiveSupplier(supplierId ?? "");
  const objectId = supplierQuery.data?.object_id ?? "";
  const deleteMut = useDeleteSupplier(supplierId ?? "", objectId);

  if (supplierQuery.isLoading || !supplierId) {
    return (
      <p className="mx-auto mt-12 max-w-3xl p-6 text-slate-500">
        {t("common.loading")}
      </p>
    );
  }
  if (supplierQuery.isError || !supplierQuery.data) {
    return (
      <p className="mx-auto mt-12 max-w-3xl p-6 text-red-700">
        {t("common.error")}
      </p>
    );
  }

  const supplier = supplierQuery.data;

  const handleSubmit = async (payload: SupplierCreate) => {
    await updateMut.mutateAsync(payload);
  };

  const handleArchive = async () => {
    if (!window.confirm(t("suppliers.archiveConfirm"))) return;
    await archiveMut.mutateAsync();
  };

  const handleDelete = async () => {
    if (!window.confirm(t("suppliers.deleteConfirm"))) return;
    try {
      await deleteMut.mutateAsync();
      navigate(`/objekte/${supplier.object_id}/lieferanten`);
    } catch (err) {
      // The 409 case (quotes reference this supplier) carries a German
      // message we surface via alert(); a richer toast UI is out of scope.
      const msg = err instanceof Error ? err.message : String(err);
      window.alert(msg);
    }
  };

  return (
    <section className="mx-auto mt-8 max-w-3xl p-6">
      <header className="mb-6">
        <h2 className="text-2xl font-semibold">{supplier.name}</h2>
        <p className="text-slate-500">
          {supplier.contact_email ?? "—"}
          {supplier.archived_at && ` · ${t("suppliers.archived")}`}
        </p>
        <nav className="mt-3 text-sm">
          <Link
            to={`/objekte/${supplier.object_id}/lieferanten`}
            className="text-slate-500 hover:underline"
          >
            ← {t("suppliers.backToList")}
          </Link>
        </nav>
      </header>

      <section className="mb-8">
        <h3 className="mb-3 text-lg font-medium">{t("suppliers.edit")}</h3>
        <SupplierForm
          initial={{
            name: supplier.name,
            contact_email: supplier.contact_email,
            contact_phone: supplier.contact_phone,
            address: supplier.address,
            notes: supplier.notes,
          }}
          onSubmit={handleSubmit}
          submitting={updateMut.isPending}
        />
      </section>

      <section className="border-t border-slate-200 pt-4">
        <div className="flex gap-2">
          {!supplier.archived_at && (
            <button
              type="button"
              onClick={() => void handleArchive()}
              className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
            >
              {t("suppliers.archive")}
            </button>
          )}
          <button
            type="button"
            onClick={() => void handleDelete()}
            className="rounded border border-red-300 px-3 py-1 text-sm text-red-700 hover:bg-red-50"
          >
            {t("suppliers.delete")}
          </button>
        </div>
      </section>
    </section>
  );
}
