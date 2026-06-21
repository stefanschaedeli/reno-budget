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

const STATUS_DOT: Record<CostStatus, string> = {
  idea: "bg-ink-subtle",
  planned: "bg-warning",
  in_progress: "bg-accent",
  completed: "bg-positive",
  cancelled: "bg-rule",
};

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
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-5">
      {groups.map(({ status, items: group }) => (
        <div
          key={status}
          onDragOver={(e) => onDragOver(e, status)}
          onDragLeave={() => setDragOverCol(null)}
          onDrop={(e) => onDrop(e, status)}
          className={`flex min-h-32 flex-col rounded-sheet border bg-paper-sunk/40 p-3 transition ${
            dragOverCol === status
              ? "border-accent bg-accent-soft/30"
              : "border-rule"
          }`}
        >
          <h3 className="mb-3 flex items-center gap-2 font-display text-sm uppercase tracking-[0.12em] text-ink">
            <span
              aria-hidden
              className={`inline-block h-1.5 w-1.5 rounded-full ${
                // eslint-disable-next-line security/detect-object-injection -- status is CostStatus literal union
                STATUS_DOT[status]
              }`}
            />
            <span>{t(`costs.status.${status}`)}</span>
            <span className="ml-auto font-mono text-xs font-normal text-ink-subtle">
              {group.length}
            </span>
          </h3>
          <div className="flex flex-col gap-2">
            {group.map((item) => (
              <div
                key={item.id}
                draggable
                onDragStart={(e) => onDragStart(e, item.id)}
                onClick={() => onCardClick(item)}
                className="cursor-grab rounded-sheet border border-rule bg-paper-raised p-3 text-sm text-ink transition hover:border-ink/30 active:cursor-grabbing"
              >
                <div className="font-medium leading-snug">{item.title}</div>
                <div className="mt-2 flex items-center justify-between text-xs text-ink-muted">
                  <span className="rounded-sheet border border-rule px-1.5 py-0.5 font-mono text-[0.65rem]">
                    {item.bkp_code ?? t("costs.uncategorised")}
                  </span>
                  <span className="font-mono tabular-nums">
                    {item.planned_year ?? "—"}
                  </span>
                </div>
                <div className="mt-2 text-right font-mono text-sm font-medium tabular-nums text-ink">
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
