// frontend/src/features/projects/ProjectCostItemsSection.tsx
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Drawer } from "@/components/Drawer";
import { useCostItems, useCreateCostItem, updateCostItem } from "@/api/costs";
import { formatChf } from "@/features/costs/types";
import { CostItemForm } from "@/features/costs/CostItemForm";
import type { CostItem, CostItemInput } from "@/features/costs/types";
import { assignTag } from "@/features/tags/api";
import type { Tag } from "@/features/tags/types";
import type { ObjectDetail } from "@/features/objects/types";
import { LinkExistingItemsDialog } from "./LinkExistingItemsDialog";

export interface ProjectCostItemsSectionProps {
  objectId: string;
  projectId: string;
  object: ObjectDetail;
  onItemsChanged?: (() => void) | undefined;
}

export function ProjectCostItemsSection({
  objectId,
  projectId,
  object,
  onItemsChanged,
}: ProjectCostItemsSectionProps): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const itemsQuery = useCostItems(objectId, { project_id: projectId });
  const items = itemsQuery.data ?? [];

  const [creating, setCreating] = useState(false);
  const [linking, setLinking] = useState(false);

  const createMut = useCreateCostItem(objectId);

  const handleCreate = async (
    payload: CostItemInput,
    pendingTags: Tag[],
  ): Promise<void> => {
    const created = await createMut.mutateAsync({
      ...payload,
      project_id: projectId,
    });
    for (const tag of pendingTags) {
      await assignTag(tag.id, {
        target_type: "cost_item",
        target_id: created.id,
      });
    }
    setCreating(false);
    onItemsChanged?.();
  };

  const handleUnlink = async (item: CostItem): Promise<void> => {
    if (!window.confirm(t("projects.costItems.removeConfirm"))) return;
    await updateCostItem(objectId, item.id, { project_id: null });
    void qc.invalidateQueries({ queryKey: ["cost-items", objectId] });
    onItemsChanged?.();
  };

  return (
    <section className="mb-8">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-lg font-medium">{t("projects.costItems.title")}</h3>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setLinking(true)}
            className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
          >
            {t("projects.costItems.link")}
          </button>
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
          >
            {t("projects.costItems.add")}
          </button>
        </div>
      </div>

      {itemsQuery.isLoading && (
        <p className="text-slate-500">{t("common.loading")}</p>
      )}
      {!itemsQuery.isLoading && items.length === 0 && (
        <p className="text-slate-500">{t("projects.costItems.empty")}</p>
      )}
      {items.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
              <th className="px-2 py-2">{t("costs.fields.title")}</th>
              <th className="px-2 py-2">{t("costs.fields.bkp")}</th>
              <th className="px-2 py-2 text-right">
                {t("costs.fields.plannedAmount")}
              </th>
              <th className="px-2 py-2" />
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b border-slate-200">
                <td
                  className="cursor-pointer px-2 py-2 font-medium hover:underline"
                  onClick={() =>
                    navigate(`/objekte/${objectId}/kosten?edit=${item.id}`)
                  }
                >
                  {item.title}
                </td>
                <td className="px-2 py-2 font-mono text-xs">
                  {item.bkp_code ?? t("costs.uncategorised")}
                </td>
                <td className="px-2 py-2 text-right tabular-nums">
                  {formatChf(item.planned_amount_chf)}
                </td>
                <td className="px-2 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => void handleUnlink(item)}
                    className="text-xs text-slate-500 hover:text-red-700"
                  >
                    {t("projects.costItems.remove")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {creating && (
        <Drawer
          title={t("projects.costItems.add")}
          onClose={() => setCreating(false)}
        >
          <CostItemForm
            units={object.units}
            objectId={objectId}
            initial={{ project_id: projectId }}
            onSubmit={handleCreate}
            onCancel={() => setCreating(false)}
            submitting={createMut.isPending}
          />
        </Drawer>
      )}

      {linking && (
        <LinkExistingItemsDialog
          objectId={objectId}
          projectId={projectId}
          onClose={() => setLinking(false)}
          onLinked={() => {
            setLinking(false);
            onItemsChanged?.();
          }}
        />
      )}
    </section>
  );
}
