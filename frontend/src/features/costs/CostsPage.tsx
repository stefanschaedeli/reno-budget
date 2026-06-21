import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { Drawer } from "@/components/Drawer";
import { apiErrorMessage } from "@/lib/apiError";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import {
  useCostItems,
  useCreateCostItem,
  useDeleteCostItem,
  useUpdateCostItem,
} from "@/api/costs";
import { getObject } from "@/features/objects/api";
import type { ObjectDetail } from "@/features/objects/types";
import { assignTag, useTags } from "@/features/tags/api";
import type { Tag } from "@/features/tags/types";
import { CostItemBoard } from "./CostItemBoard";
import { CostItemFilters } from "./CostItemFilters";
import { CostItemForm } from "./CostItemForm";
import { CostItemList } from "./CostItemList";
import type { CostItem, CostItemFilters as Filters, CostItemInput } from "./types";

/**
 * Top-level page for an object's cost items. Composes filters + tab
 * switch (Liste / Board) + create/edit drawer. The page owns the
 * "currently editing" item state; the form is reused for both create
 * and edit.
 */
export function CostsPage(): JSX.Element {
  const { t } = useTranslation();
  const { objectId } = useParams<{ objectId: string }>();
  const [obj, setObj] = useState<ObjectDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tab, setTab] = useState<"list" | "board">("list");
  const [filters, setFilters] = useState<Filters>({});
  const [editing, setEditing] = useState<CostItem | "new" | null>(null);
  const [tagAssignError, setTagAssignError] = useState<string | null>(null);

  useEffect(() => {
    if (!objectId) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await getObject(objectId);
        if (!cancelled) setObj(data);
      } catch (e) {
        if (!cancelled)
          setLoadError(apiErrorMessage(e, t("common.error")));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [objectId, t]);

  const costItemsQuery = useCostItems(objectId ?? "", {
    ...filters,
    include_tag_ids: true,
    include_lot_ids: true,
  });
  const tagsQuery = useTags(objectId ?? "");
  const createMut = useCreateCostItem(objectId ?? "");
  const updateMut = useUpdateCostItem(
    objectId ?? "",
    editing && editing !== "new" ? editing.id : "",
  );
  const deleteMut = useDeleteCostItem(objectId ?? "");

  if (loadError)
    return (
      <PageContainer width="wide">
        <p className="text-negative">{loadError}</p>
      </PageContainer>
    );
  if (!obj || !objectId)
    return (
      <PageContainer width="wide">
        <p className="text-ink-muted">{t("common.loading")}</p>
      </PageContainer>
    );

  const handleSubmit = async (payload: CostItemInput, pendingTags: Tag[]) => {
    if (editing === "new") {
      const created = await createMut.mutateAsync(payload);
      // Assign any tags the user picked during creation. The form holds them
      // locally until the cost item id exists; now that it does, fan out the
      // assignments. Failures are non-fatal: the item was created and the
      // user can retry from the detail/edit view.
      if (pendingTags.length > 0) {
        const results = await Promise.allSettled(
          pendingTags.map((tag) =>
            assignTag(tag.id, {
              target_type: "cost_item",
              target_id: created.id,
            }),
          ),
        );
        const failed = results.filter((r) => r.status === "rejected").length;
        if (failed > 0) {
          setTagAssignError(t("costs.tagAssignPartial", { count: failed }));
        }
      }
    } else if (editing) {
      await updateMut.mutateAsync(payload);
    }
    setEditing(null);
  };

  const handleDelete = async (item: CostItem) => {
    if (!window.confirm(t("costs.deleteConfirm"))) return;
    await deleteMut.mutateAsync(item.id);
    setEditing(null);
  };

  const items = costItemsQuery.data ?? [];

  return (
    <PageContainer width="wide">
      <PageHeader
        title={t("costs.title")}
        subtitle={obj.name}
        actions={
          <button
            type="button"
            onClick={() => setEditing("new")}
            className="rounded bg-ink px-3 py-1 text-sm text-paper hover:bg-ink"
          >
            {t("costs.create")}
          </button>
        }
      />

      <CostItemFilters
        units={obj.units}
        objectId={objectId}
        onChange={setFilters}
      />

      <div className="mb-3 flex gap-2 border-b border-rule">
        <button
          type="button"
          onClick={() => setTab("list")}
          aria-pressed={tab === "list"}
          className={`px-3 py-1 text-sm ${
            tab === "list"
              ? "border-b-2 border-ink font-medium"
              : "text-ink-muted"
          }`}
        >
          {t("costs.tabs.list")}
        </button>
        <button
          type="button"
          onClick={() => setTab("board")}
          aria-pressed={tab === "board"}
          className={`px-3 py-1 text-sm ${
            tab === "board"
              ? "border-b-2 border-ink font-medium"
              : "text-ink-muted"
          }`}
        >
          {t("costs.tabs.board")}
        </button>
      </div>

      {tagAssignError && (
        <div
          role="alert"
          className="mb-3 rounded border border-warning bg-warning-soft px-3 py-2 text-sm text-ink"
        >
          <div className="flex items-center justify-between gap-2">
            <span>{tagAssignError}</span>
            <button
              type="button"
              onClick={() => setTagAssignError(null)}
              aria-label={t("common.close")}
              className="text-ink underline-offset-2 hover:text-accent hover:underline"
            >
              ×
            </button>
          </div>
        </div>
      )}
      {costItemsQuery.isLoading && (
        <p className="text-ink-muted">{t("common.loading")}</p>
      )}
      {costItemsQuery.isError && (
        <p className="text-negative">{t("common.error")}</p>
      )}
      {!costItemsQuery.isLoading && !costItemsQuery.isError && (
        <>
          {tab === "list" ? (
            <CostItemList
              items={items}
              tags={tagsQuery.data ?? []}
              onRowClick={(c) => setEditing(c)}
            />
          ) : (
            <CostItemBoard
              objectId={objectId}
              items={items}
              onCardClick={(c) => setEditing(c)}
            />
          )}
        </>
      )}

      {editing !== null && (
        <Drawer
          title={
            editing === "new" ? t("costs.create") : t("costs.edit")
          }
          onClose={() => setEditing(null)}
        >
          <CostItemForm
            units={obj.units}
            objectId={objectId}
            costItemId={editing !== "new" ? editing.id : undefined}
            initial={
              editing === "new"
                ? undefined
                : {
                    bkp_code: editing.bkp_code,
                    project_id: editing.project_id ?? null,
                    npk_code: editing.npk_code,
                    title: editing.title,
                    description: editing.description,
                    status: editing.status,
                    priority: editing.priority,
                    planned_year: editing.planned_year,
                    planned_amount_chf: editing.planned_amount_chf,
                    actual_amount_chf: editing.actual_amount_chf,
                    actual_date: editing.actual_date,
                    lifespan_years: editing.lifespan_years,
                    warranty_until: editing.warranty_until,
                    scope: editing.scope,
                    allocations: editing.allocations,
                    bkp_allocations: editing.bkp_allocations,
                  }
            }
            onSubmit={handleSubmit}
            onCancel={() => setEditing(null)}
            submitting={createMut.isPending || updateMut.isPending}
          />
          {editing !== "new" && (
            <div className="mt-4 border-t border-rule pt-3 text-right">
              <button
                type="button"
                onClick={() => void handleDelete(editing)}
                className="rounded border border-negative px-3 py-1 text-sm text-negative hover:bg-negative-soft"
              >
                {t("costs.delete")}
              </button>
            </div>
          )}
        </Drawer>
      )}
    </PageContainer>
  );
}
