/**
 * Lot detail / edit page.
 *
 * Shows lot metadata, an edit form, archive + delete buttons, the list
 * of member cost items (with add / remove actions), tag chips and a
 * total budget rollup (sum of planned amounts of member cost items).
 */
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useCostItems } from "@/api/costs";
import { TagChip } from "@/components/TagChip";
import { formatChf } from "@/features/costs/types";
import { useTagsForTarget } from "@/features/tags/api";
import { LotForm } from "./LotForm";
import {
  useAddCostItemToLot,
  useArchiveLot,
  useDeleteLot,
  useLot,
  useLotCostItems,
  useRemoveCostItemFromLot,
  useUpdateLot,
} from "./api";
import type { LotCreate } from "./types";

export function LotDetailPage(): JSX.Element {
  const { t } = useTranslation();
  const { lotId } = useParams<{ lotId: string }>();
  const navigate = useNavigate();
  const [pickerOpen, setPickerOpen] = useState(false);

  const lotQuery = useLot(lotId ?? "");
  const updateMut = useUpdateLot(lotId ?? "");
  const archiveMut = useArchiveLot(lotId ?? "");
  const objectId = lotQuery.data?.object_id ?? "";
  const deleteMut = useDeleteLot(lotId ?? "", objectId);
  const memberQuery = useLotCostItems(lotId ?? "");
  const allItemsQuery = useCostItems(objectId, {});
  const tagsQuery = useTagsForTarget("lot", lotId ?? "");
  const addMut = useAddCostItemToLot(lotId ?? "");
  const removeMut = useRemoveCostItemFromLot(lotId ?? "");

  const members = useMemo(() => memberQuery.data ?? [], [memberQuery.data]);
  const memberIds = useMemo(() => new Set(members.map((m) => m.id)), [members]);
  const candidates = useMemo(
    () => (allItemsQuery.data ?? []).filter((c) => !memberIds.has(c.id)),
    [allItemsQuery.data, memberIds],
  );

  const total = useMemo(
    () =>
      members.reduce((acc, m) => {
        const v = m.planned_amount_chf ? Number(m.planned_amount_chf) : 0;
        return Number.isNaN(v) ? acc : acc + v;
      }, 0),
    [members],
  );

  if (lotQuery.isLoading || !lotId) {
    return (
      <p className="mx-auto mt-12 max-w-3xl p-6 text-slate-500">
        {t("common.loading")}
      </p>
    );
  }
  if (lotQuery.isError || !lotQuery.data) {
    return (
      <p className="mx-auto mt-12 max-w-3xl p-6 text-red-700">
        {t("common.error")}
      </p>
    );
  }

  const lot = lotQuery.data;
  const tags = tagsQuery.data ?? [];

  const handleSubmit = async (payload: LotCreate) => {
    await updateMut.mutateAsync(payload);
  };

  const handleArchive = async () => {
    if (!window.confirm(t("lots.archiveConfirm"))) return;
    await archiveMut.mutateAsync();
  };

  const handleDelete = async () => {
    if (!window.confirm(t("lots.deleteConfirm"))) return;
    await deleteMut.mutateAsync();
    navigate(`/objekte/${lot.object_id}/lose`);
  };

  const handleAdd = async (costItemId: string) => {
    await addMut.mutateAsync(costItemId);
    setPickerOpen(false);
  };

  const handleRemove = async (costItemId: string) => {
    if (!window.confirm(t("lots.removeMemberConfirm"))) return;
    await removeMut.mutateAsync(costItemId);
  };

  return (
    <section className="mx-auto mt-8 max-w-3xl p-6">
      <header className="mb-6">
        <h2 className="text-2xl font-semibold">{lot.name}</h2>
        <p className="text-slate-500">
          {t(`lots.status.${lot.status}`)}
          {lot.tender_deadline &&
            ` · ${new Date(lot.tender_deadline).toLocaleDateString("de-CH")}`}
          {lot.archived_at && ` · ${t("lots.archived")}`}
        </p>
        <nav className="mt-3 text-sm">
          <Link
            to={`/objekte/${lot.object_id}/lose`}
            className="text-slate-500 hover:underline"
          >
            ← {t("lots.backToList")}
          </Link>
        </nav>
      </header>

      {tags.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-1">
          {tags.map((tag) => (
            <TagChip key={tag.id} tag={tag} />
          ))}
        </div>
      )}

      <section className="mb-8">
        <h3 className="mb-3 text-lg font-medium">{t("lots.edit")}</h3>
        <LotForm
          initial={{
            name: lot.name,
            description: lot.description,
            status: lot.status,
            tender_deadline: lot.tender_deadline,
          }}
          onSubmit={handleSubmit}
          submitting={updateMut.isPending}
        />
      </section>

      <section className="mb-8">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-medium">{t("lots.members.title")}</h3>
          <div className="flex items-center gap-3">
            <p className="text-sm text-slate-500">
              {t("lots.members.total")}: <span className="tabular-nums font-medium">{formatChf(total.toFixed(2))}</span>
            </p>
            <button
              type="button"
              onClick={() => setPickerOpen((v) => !v)}
              className="rounded border border-slate-300 px-2 py-1 text-sm hover:bg-slate-100"
            >
              {t("lots.members.add")}
            </button>
          </div>
        </div>

        {pickerOpen && (
          <div className="mb-3 rounded border border-slate-200 bg-slate-50 p-3">
            {candidates.length === 0 ? (
              <p className="text-sm text-slate-500">
                {t("lots.members.noCandidates")}
              </p>
            ) : (
              <ul className="max-h-60 space-y-1 overflow-y-auto text-sm">
                {candidates.map((c) => (
                  <li
                    key={c.id}
                    className="flex items-center justify-between rounded px-2 py-1 hover:bg-white"
                  >
                    <span>
                      {c.title}{" "}
                      <span className="font-mono text-xs text-slate-500">
                        {c.bkp_code ?? "—"}
                      </span>
                    </span>
                    <button
                      type="button"
                      onClick={() => void handleAdd(c.id)}
                      className="rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-100"
                    >
                      {t("lots.members.addThis")}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {memberQuery.isLoading && (
          <p className="text-slate-500">{t("common.loading")}</p>
        )}
        {members.length === 0 && !memberQuery.isLoading && (
          <p className="text-slate-500">{t("lots.members.empty")}</p>
        )}
        {members.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-600">
              <tr className="border-b border-slate-300">
                <th className="px-2 py-2">{t("costs.fields.title")}</th>
                <th className="px-2 py-2">{t("costs.fields.bkp")}</th>
                <th className="px-2 py-2 text-right">
                  {t("costs.fields.plannedAmount")}
                </th>
                <th className="px-2 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {members.map((item) => (
                <tr
                  key={item.id}
                  data-testid={`member-row-${item.id}`}
                  className="border-b border-slate-200"
                >
                  <td className="px-2 py-2 font-medium">{item.title}</td>
                  <td className="px-2 py-2 font-mono text-xs">
                    {item.bkp_code ?? t("costs.uncategorised")}
                  </td>
                  <td className="px-2 py-2 text-right tabular-nums">
                    {formatChf(item.planned_amount_chf)}
                  </td>
                  <td className="px-2 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => void handleRemove(item.id)}
                      className="rounded border border-red-300 px-2 py-0.5 text-xs text-red-700 hover:bg-red-50"
                    >
                      {t("lots.members.remove")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="border-t border-slate-200 pt-4">
        <div className="flex gap-2">
          {!lot.archived_at && (
            <button
              type="button"
              onClick={() => void handleArchive()}
              className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
            >
              {t("lots.archive")}
            </button>
          )}
          <button
            type="button"
            onClick={() => void handleDelete()}
            className="rounded border border-red-300 px-3 py-1 text-sm text-red-700 hover:bg-red-50"
          >
            {t("lots.delete")}
          </button>
        </div>
      </section>
    </section>
  );
}
