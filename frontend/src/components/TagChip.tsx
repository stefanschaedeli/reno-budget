/**
 * Tiny pill rendering a tag as ``key: value`` with an optional colour.
 *
 * The colour is applied as the chip's left border; the body keeps the
 * neutral paper palette so chips stay readable on dense lists. An
 * optional ``onRemove`` callback turns the chip into a deletable pill.
 */
import type { Tag } from "@/features/tags/types";

export interface TagChipProps {
  tag: Tag;
  onRemove?: (() => void) | undefined;
  className?: string;
}

export function TagChip({ tag, onRemove, className }: TagChipProps): JSX.Element {
  const accent = tag.color ?? "#B5651D"; // ochre fallback
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-sheet border border-rule bg-paper-raised px-2 py-0.5 text-xs ${className ?? ""}`}
      style={{ borderLeftColor: accent, borderLeftWidth: 3 }}
      data-testid={`tag-chip-${tag.id}`}
    >
      <span className="font-medium text-ink">{tag.key}</span>
      <span className="text-ink-subtle">:</span>
      <span className="text-ink-muted">{tag.value}</span>
      {onRemove && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          aria-label="Tag entfernen"
          className="ml-1 text-ink-subtle hover:text-negative"
        >
          ×
        </button>
      )}
    </span>
  );
}
