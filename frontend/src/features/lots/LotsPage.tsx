/**
 * Per-object lot list view.
 *
 * Shows one row per lot with status, tender deadline, archived state and
 * the membership count (returned by the backend). Provides inline create
 * via a drawer. Mirrors the ProjectsPage layout.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { LotForm } from "./LotForm";
import { useCreateLot, useLots } from "./api";
import type { Lot, LotCreate } from "./types";

export function LotsPage(): JSX.Element {
  const { t } = useTranslation();
  const { objectId } = useParams<{ objectId: string }>();
  const [includeArchived, setIncludeArchived] = useState(false);
  const [creating, setCreating] = useState(false);

  const lotsQuery = useLots(objectId ?? "", { includeArchived });
  const createMut = useCreateLot(objectId ?? "");

  if (!objectId) {
    return (
      <p className="mx-auto mt-12 max-w-5xl p-6 text-red-700">
        {t("common.error")}
      </p>
    );
  }

  const lots = lotsQuery.data ?? [];

  const handleCreate = async (payload: LotCreate) => {
    await createMut.mutateAsync(payload);
    setCreating(false);
  };

  return (
    <section className="mx-auto mt-8 max-w-5xl p-6">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">{t("lots.title")}</h2>
          <p className="text-slate-500">{t("lots.subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
        >
          {t("lots.create")}
        </button>
      </header>

      <label className="mb-3 inline-flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
        />
        {t("lots.includeArchived")}
      </label>

      {lotsQuery.isLoading && (
        <p className="text-slate-500">{t("common.loading")}</p>
      )}
      {lotsQuery.isError && (
        <p className="text-red-700">{t("common.error")}</p>
      )}
      {lotsQuery.isSuccess && lots.length === 0 && (
        <p className="text-slate-500">{t("lots.empty")}</p>
      )}
      {lots.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
              <th className="px-2 py-2">{t("lots.fields.name")}</th>
              <th className="px-2 py-2">{t("lots.fields.status")}</th>
              <th className="px-2 py-2">{t("lots.fields.tenderDeadline")}</th>
              <th className="px-2 py-2 text-right">
                {t("lots.fields.itemCount")}
              </th>
              <th className="px-2 py-2">{t("lots.fields.archivedAt")}</th>
            </tr>
          </thead>
          <tbody>
            {lots.map((l: Lot) => (
              <tr
                key={l.id}
                data-testid={`lot-row-${l.id}`}
                className="border-b border-slate-200 hover:bg-slate-50"
              >
                <td className="px-2 py-2 font-medium">
                  <Link to={`/lose/${l.id}`} className="hover:underline">
                    {l.name}
                  </Link>
                </td>
                <td className="px-2 py-2">{t(`lots.status.${l.status}`)}</td>
                <td className="px-2 py-2">
                  {l.tender_deadline
                    ? new Date(l.tender_deadline).toLocaleDateString("de-CH")
                    : "—"}
                </td>
                <td className="px-2 py-2 text-right tabular-nums">
                  {l.cost_item_count}
                </td>
                <td className="px-2 py-2 text-slate-500">
                  {l.archived_at
                    ? new Date(l.archived_at).toLocaleDateString("de-CH")
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {creating && (
        <Drawer title={t("lots.create")} onClose={() => setCreating(false)}>
          <LotForm
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
