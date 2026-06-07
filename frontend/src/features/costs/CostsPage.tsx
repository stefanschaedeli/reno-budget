import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import {
  useCostItems,
  useCreateCostItem,
  useDeleteCostItem,
  useUpdateCostItem,
} from "@/api/costs";
import { getObject } from "@/features/objects/api";
import type { ObjectDetail } from "@/features/objects/types";
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

  useEffect(() => {
    if (!objectId) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await getObject(objectId);
        if (!cancelled) setObj(data);
      } catch (e) {
        if (!cancelled)
          setLoadError(
            e instanceof ApiError ? String(e.detail) : t("common.error"),
          );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [objectId, t]);

  const costItemsQuery = useCostItems(objectId ?? "", filters);
  const createMut = useCreateCostItem(objectId ?? "");
  const updateMut = useUpdateCostItem(
    objectId ?? "",
    editing && editing !== "new" ? editing.id : "",
  );
  const deleteMut = useDeleteCostItem(objectId ?? "");

  if (loadError)
    return (
      <p className="mx-auto mt-12 max-w-5xl p-6 text-red-700">{loadError}</p>
    );
  if (!obj || !objectId)
    return (
      <p className="mx-auto mt-12 max-w-5xl p-6 text-slate-500">
        {t("common.loading")}
      </p>
    );

  const handleSubmit = async (payload: CostItemInput) => {
    if (editing === "new") {
      await createMut.mutateAsync(payload);
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
    <section className="mx-auto mt-8 max-w-6xl p-6">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">{t("costs.title")}</h2>
          <p className="text-slate-500">{obj.name}</p>
        </div>
        <button
          type="button"
          onClick={() => setEditing("new")}
          className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
        >
          {t("costs.create")}
        </button>
      </header>

      <CostItemFilters
        units={obj.units}
        objectId={objectId}
        onChange={setFilters}
      />

      <div className="mb-3 flex gap-2 border-b border-slate-200">
        <button
          type="button"
          onClick={() => setTab("list")}
          aria-pressed={tab === "list"}
          className={`px-3 py-1 text-sm ${
            tab === "list"
              ? "border-b-2 border-slate-900 font-medium"
              : "text-slate-500"
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
              ? "border-b-2 border-slate-900 font-medium"
              : "text-slate-500"
          }`}
        >
          {t("costs.tabs.board")}
        </button>
      </div>

      {costItemsQuery.isLoading && (
        <p className="text-slate-500">{t("common.loading")}</p>
      )}
      {costItemsQuery.isError && (
        <p className="text-red-700">{t("common.error")}</p>
      )}
      {!costItemsQuery.isLoading && !costItemsQuery.isError && (
        <>
          {tab === "list" ? (
            <CostItemList items={items} onRowClick={(c) => setEditing(c)} />
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
            <div className="mt-4 border-t border-slate-200 pt-3 text-right">
              <button
                type="button"
                onClick={() => void handleDelete(editing)}
                className="rounded border border-red-300 px-3 py-1 text-sm text-red-700 hover:bg-red-50"
              >
                {t("costs.delete")}
              </button>
            </div>
          )}
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
