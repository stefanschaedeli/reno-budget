import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { TagChip } from "@/components/TagChip";
import type { Tag } from "@/features/tags/types";
import { type CostItem, formatChf } from "./types";

/**
 * Sortable table of cost items. Clicking a row calls `onRowClick` so
 * the page-level drawer can open in edit mode. Sorting is client-side
 * (filtering is server-side in the data hook) since result sets here
 * are bounded by a single object's catalog.
 */
export interface CostItemListProps {
  items: CostItem[];
  /**
   * All tags defined for this object. Used to materialise tag chips per row
   * from each item's ``tag_ids`` list — the parent prefetches once and
   * passes the lookup down to avoid N+1 fetches.
   */
  tags?: Tag[];
  onRowClick: (item: CostItem) => void;
}

type SortKey =
  | "title"
  | "bkp_code"
  | "status"
  | "priority"
  | "planned_year"
  | "planned_amount_chf"
  | "actual_amount_chf";

interface SortState {
  key: SortKey;
  dir: "asc" | "desc";
}

function priorityRank(p: string): number {
  switch (p) {
    case "low":
      return 0;
    case "med":
      return 1;
    case "high":
      return 2;
    case "urgent":
      return 3;
    default:
      return -1;
  }
}

function compareItems(a: CostItem, b: CostItem, key: SortKey): number {
  switch (key) {
    case "planned_amount_chf":
      return Number(a.planned_amount_chf ?? "0") - Number(b.planned_amount_chf ?? "0");
    case "actual_amount_chf":
      return Number(a.actual_amount_chf ?? "0") - Number(b.actual_amount_chf ?? "0");
    case "planned_year": {
      const av = a.planned_year ?? -Infinity;
      const bv = b.planned_year ?? -Infinity;
      return av - bv;
    }
    case "priority":
      return priorityRank(a.priority) - priorityRank(b.priority);
    case "title":
      return a.title.localeCompare(b.title, "de");
    case "bkp_code":
      return (a.bkp_code ?? "").localeCompare(b.bkp_code ?? "", "de");
    case "status":
      return a.status.localeCompare(b.status, "de");
  }
}

export function CostItemList({
  items,
  tags = [],
  onRowClick,
}: CostItemListProps): JSX.Element {
  const { t } = useTranslation();
  const [sort, setSort] = useState<SortState>({
    key: "title",
    dir: "asc",
  });

  const tagById = useMemo(() => {
    const m = new Map<string, Tag>();
    for (const t of tags) m.set(t.id, t);
    return m;
  }, [tags]);

  const sorted = useMemo(() => {
    const copy = items.slice();
    copy.sort((a, b) => {
      const c = compareItems(a, b, sort.key);
      return sort.dir === "asc" ? c : -c;
    });
    return copy;
  }, [items, sort]);

  const toggleSort = (key: SortKey) => {
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "asc" },
    );
  };

  const arrow = (key: SortKey) =>
    sort.key === key ? (sort.dir === "asc" ? " ▲" : " ▼") : "";

  if (items.length === 0) {
    return <p className="text-slate-500">{t("costs.empty")}</p>;
  }

  const columns: Array<[SortKey, string]> = [
    ["title", t("costs.fields.title")],
    ["bkp_code", t("costs.fields.bkp")],
    ["status", t("costs.fields.status")],
    ["priority", t("costs.fields.priority")],
    ["planned_year", t("costs.fields.plannedYear")],
    ["planned_amount_chf", t("costs.fields.plannedAmount")],
    ["actual_amount_chf", t("costs.fields.actualAmount")],
  ];

  return (
    <table className="w-full text-sm">
      <thead className="text-left text-slate-600">
        <tr className="border-b border-slate-300">
          {columns.map(([key, label]) => (
            <th key={key} className="cursor-pointer px-2 py-2">
              <button
                type="button"
                onClick={() => toggleSort(key)}
                className="font-medium hover:underline"
              >
                {label}
                {arrow(key)}
              </button>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((item) => (
          <tr
            key={item.id}
            onClick={() => onRowClick(item)}
            className="cursor-pointer border-b border-slate-200 hover:bg-slate-50"
          >
            <td className="px-2 py-2 font-medium">
              <div className="flex flex-wrap items-center gap-1">
                <span>{item.title}</span>
                {item.tag_ids
                  ? item.tag_ids
                      .map((id) => tagById.get(id))
                      .filter((t): t is Tag => Boolean(t))
                      .map((tag) => <TagChip key={tag.id} tag={tag} />)
                  : null}
              </div>
            </td>
            <td className="px-2 py-2 font-mono text-xs">
              {item.bkp_code ?? (
                <span className="text-slate-400 italic">
                  {t("costs.uncategorised")}
                </span>
              )}
            </td>
            <td className="px-2 py-2">{t(`costs.status.${item.status}`)}</td>
            <td className="px-2 py-2">
              {t(`costs.priority.${item.priority}`)}
            </td>
            <td className="px-2 py-2">{item.planned_year ?? "—"}</td>
            <td className="px-2 py-2 text-right tabular-nums">
              {formatChf(item.planned_amount_chf)}
            </td>
            <td className="px-2 py-2 text-right tabular-nums">
              {formatChf(item.actual_amount_chf)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
