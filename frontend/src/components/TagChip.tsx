/**
 * Tiny pill rendering a tag as ``key: value`` with an optional colour.
 *
 * The colour is applied as the chip's left border; the body keeps the
 * neutral slate palette so chips stay readable on dense lists. An
 * optional ``onRemove`` callback turns the chip into a deletable pill.
 */
import type { Tag } from "@/features/tags/types";

export interface TagChipProps {
  tag: Tag;
  onRemove?: (() => void) | undefined;
  className?: string;
}

export function TagChip({ tag, onRemove, className }: TagChipProps): JSX.Element {
  const accent = tag.color ?? "#94a3b8"; // slate-400 fallback
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-0.5 text-xs ${className ?? ""}`}
      style={{ borderLeftColor: accent, borderLeftWidth: 3 }}
      data-testid={`tag-chip-${tag.id}`}
    >
      <span className="font-medium text-slate-700">{tag.key}</span>
      <span className="text-slate-500">:</span>
      <span className="text-slate-800">{tag.value}</span>
      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          aria-label="Tag entfernen"
          className="ml-1 text-slate-400 hover:text-slate-700"
        >
          ×
        </button>
      )}
    </span>
  );
}
