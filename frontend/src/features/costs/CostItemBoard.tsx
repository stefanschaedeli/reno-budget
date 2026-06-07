import { useState, type DragEvent } from "react";
import { useTranslation } from "react-i18next";
import { useUpdateCostItemStatus } from "@/api/costs";
import {
  COST_STATUSES,
  type CostItem,
  type CostStatus,
  formatChf,
} from "./types";

/**
 * Kanban board grouped by {@link CostStatus}. Drag-and-drop changes
 * status via {@link useUpdateCostItemStatus} which applies an optimistic
 * cache patch and rolls back on error. No external DnD lib — vanilla
 * HTML5 drag events suffice for a five-column board.
 */
export interface CostItemBoardProps {
  objectId: string;
  items: CostItem[];
  onCardClick: (item: CostItem) => void;
}

export function CostItemBoard({
  objectId,
  items,
  onCardClick,
}: CostItemBoardProps): JSX.Element {
  const { t } = useTranslation();
  const updateStatus = useUpdateCostItemStatus(objectId);
  const [dragOverCol, setDragOverCol] = useState<CostStatus | null>(null);

  const groups = COST_STATUSES.map((status) => ({
    status,
    items: items.filter((i) => i.status === status),
  }));

  const onDragStart = (e: DragEvent<HTMLDivElement>, id: string) => {
    e.dataTransfer.setData("text/plain", id);
    e.dataTransfer.effectAllowed = "move";
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>, status: CostStatus) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (dragOverCol !== status) setDragOverCol(status);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>, status: CostStatus) => {
    e.preventDefault();
    setDragOverCol(null);
    const costItemId = e.dataTransfer.getData("text/plain");
    if (!costItemId) return;
    const current = items.find((i) => i.id === costItemId);
    if (!current || current.status === status) return;
    updateStatus.mutate({ costItemId, status });
  };

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3 lg:grid-cols-5">
      {groups.map(({ status, items: group }) => (
        <div
          key={status}
          onDragOver={(e) => onDragOver(e, status)}
          onDragLeave={() => setDragOverCol(null)}
          onDrop={(e) => onDrop(e, status)}
          className={`flex min-h-32 flex-col rounded border p-2 ${
            dragOverCol === status
              ? "border-slate-900 bg-slate-100"
              : "border-slate-200 bg-slate-50"
          }`}
        >
          <h3 className="mb-2 text-sm font-semibold text-slate-700">
            {t(`costs.status.${status}`)}{" "}
            <span className="text-xs font-normal text-slate-500">
              ({group.length})
            </span>
          </h3>
          <div className="flex flex-col gap-2">
            {group.map((item) => (
              <div
                key={item.id}
                draggable
                onDragStart={(e) => onDragStart(e, item.id)}
                onClick={() => onCardClick(item)}
                className="cursor-grab rounded border border-slate-300 bg-white p-2 text-sm shadow-sm hover:shadow active:cursor-grabbing"
              >
                <div className="font-medium">{item.title}</div>
                <div className="mt-1 flex items-center justify-between text-xs text-slate-600">
                  <span className="rounded bg-slate-200 px-1 font-mono">
                    {item.bkp_code ?? t("costs.uncategorised")}
                  </span>
                  <span>{item.planned_year ?? "—"}</span>
                </div>
                <div className="mt-1 text-right text-xs tabular-nums">
                  {formatChf(item.planned_amount_chf)}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
