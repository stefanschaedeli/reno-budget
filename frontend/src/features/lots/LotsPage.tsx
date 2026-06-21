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
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { Drawer } from "@/components/Drawer";

export function LotsPage(): JSX.Element {
  const { t } = useTranslation();
  const { objectId } = useParams<{ objectId: string }>();
  const [includeArchived, setIncludeArchived] = useState(false);
  const [creating, setCreating] = useState(false);

  const lotsQuery = useLots(objectId ?? "", { includeArchived });
  const createMut = useCreateLot(objectId ?? "");

  if (!objectId) {
    return (
      <PageContainer width="default">
        <p className="text-negative">{t("common.error")}</p>
      </PageContainer>
    );
  }

  const lots = lotsQuery.data ?? [];

  const handleCreate = async (payload: LotCreate) => {
    await createMut.mutateAsync(payload);
    setCreating(false);
  };

  return (
    <PageContainer width="default">
      <PageHeader
        title={t("lots.title")}
        subtitle={t("lots.subtitle")}
        actions={
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded bg-ink px-3 py-1 text-sm text-paper hover:bg-ink"
          >
            {t("lots.create")}
          </button>
        }
      />

      <label className="mb-3 inline-flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
        />
        {t("lots.includeArchived")}
      </label>

      {lotsQuery.isLoading && (
        <p className="text-ink-muted">{t("common.loading")}</p>
      )}
      {lotsQuery.isError && (
        <p className="text-negative">{t("common.error")}</p>
      )}
      {lotsQuery.isSuccess && lots.length === 0 && (
        <p className="text-ink-muted">{t("lots.empty")}</p>
      )}
      {lots.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-ink-muted">
            <tr className="border-b border-rule">
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
                className="border-b border-rule hover:bg-paper-sunk"
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
                <td className="px-2 py-2 text-ink-muted">
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
    </PageContainer>
  );
}
