// frontend/src/features/projects/LinkExistingItemsDialog.tsx
import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { useCostItems, updateCostItem } from "@/api/costs";

export interface LinkExistingItemsDialogProps {
  objectId: string;
  projectId: string;
  onClose: () => void;
  onLinked: () => void;
}

export function LinkExistingItemsDialog({
  objectId,
  projectId,
  onClose,
  onLinked,
}: LinkExistingItemsDialogProps): JSX.Element {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const itemsQuery = useCostItems(objectId, { project_id_is_null: true });
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const items = itemsQuery.data ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) => i.title.toLowerCase().includes(q));
  }, [items, search]);

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const handleConfirm = async () => {
    if (selected.size === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const ids = Array.from(selected);
      for (const id of ids) {
        await updateCostItem(objectId, id, { project_id: projectId });
      }
      void qc.invalidateQueries({ queryKey: ["cost-items", objectId] });
      onLinked();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-40 flex items-center justify-center bg-ink/40 p-4"
    >
      <div className="w-full max-w-md rounded-sheet border border-rule bg-paper-raised p-5 shadow-panel">
        <h3 className="mb-4 font-display text-xl text-ink">
          {t("projects.costItems.linkDialog.title")}
        </h3>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("projects.costItems.linkDialog.search")}
          className="mb-3 w-full rounded-sheet border border-rule bg-paper px-2 py-1.5 text-sm text-ink focus:border-accent focus:outline-none"
        />
        <div className="max-h-64 overflow-y-auto border border-rule">
          {itemsQuery.isLoading && (
            <p className="p-3 text-sm text-ink-muted">{t("common.loading")}</p>
          )}
          {!itemsQuery.isLoading && filtered.length === 0 && (
            <p className="p-3 text-sm text-ink-muted">
              {t("projects.costItems.linkDialog.empty")}
            </p>
          )}
          {filtered.map((i) => (
            <label
              key={i.id}
              className="flex cursor-pointer items-center gap-2 border-b border-rule px-3 py-2 text-sm text-ink last:border-b-0 hover:bg-paper-sunk"
            >
              <input
                type="checkbox"
                aria-label={i.title}
                checked={selected.has(i.id)}
                onChange={() => toggle(i.id)}
                className="accent-ink"
              />
              <span>{i.title}</span>
            </label>
          ))}
        </div>
        {error && (
          <p className="mt-2 text-xs text-negative">{error}</p>
        )}
        <div className="mt-4 flex items-center justify-between">
          <span className="text-xs text-ink-muted">
            {t("projects.costItems.linkDialog.selected", { count: selected.size })}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-sheet border border-rule px-3 py-1.5 text-sm text-ink-muted hover:border-ink/30 hover:text-ink"
            >
              {t("projects.costItems.linkDialog.cancel")}
            </button>
            <button
              type="button"
              onClick={() => void handleConfirm()}
              disabled={selected.size === 0 || submitting}
              className="rounded-sheet bg-ink px-3 py-1.5 text-sm text-paper hover:bg-ink/85 disabled:opacity-50"
            >
              {t("projects.costItems.linkDialog.confirm")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
