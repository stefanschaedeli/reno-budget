/**
 * Autocomplete-style tag input.
 *
 * Loads the object's tag catalogue via {@link useTags} and presents a
 * filterable dropdown. Selected tags appear as removable chips above
 * the input. The "Neuen Tag anlegen" affordance appears when the user's
 * query doesn't match an existing tag and is parseable as ``key:value``
 * (or a bare key, which the user can complete inline).
 *
 * The picker is fully controlled — it never persists tag selections on
 * its own. Parents wire {@link onChange} to a form state or directly to
 * the assign/unassign mutations.
 */
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { TagChip } from "./TagChip";
import { useCreateTag, useTags } from "@/features/tags/api";
import type { Tag } from "@/features/tags/types";

export interface TagPickerProps {
  objectId: string;
  value: Tag[];
  onChange: (next: Tag[]) => void;
  /** Hide the inline create-new affordance (e.g. read-only filter use). */
  allowCreate?: boolean;
  placeholder?: string;
}

function parseKeyValue(input: string): { key: string; value: string } | null {
  const trimmed = input.trim();
  if (!trimmed) return null;
  const idx = trimmed.indexOf(":");
  if (idx <= 0 || idx === trimmed.length - 1) return null;
  const key = trimmed.slice(0, idx).trim();
  const value = trimmed.slice(idx + 1).trim();
  if (!key || !value) return null;
  return { key, value };
}

export function TagPicker({
  objectId,
  value,
  onChange,
  allowCreate = true,
  placeholder,
}: TagPickerProps): JSX.Element {
  const { t } = useTranslation();
  const tagsQuery = useTags(objectId);
  const createMut = useCreateTag(objectId);
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);

  const all = useMemo(() => tagsQuery.data ?? [], [tagsQuery.data]);

  const matches = useMemo(() => {
    const selectedIds = new Set(value.map((v) => v.id));
    const q = query.trim().toLowerCase();
    return all
      .filter((tag) => !selectedIds.has(tag.id))
      .filter((tag) => {
        if (!q) return true;
        const haystack = `${tag.key}:${tag.value}`.toLowerCase();
        return haystack.includes(q);
      })
      .slice(0, 20);
  }, [all, query, value]);

  const parsedNew = parseKeyValue(query);
  const exactMatch = parsedNew
    ? all.find(
        (tag) =>
          tag.key.toLowerCase() === parsedNew.key.toLowerCase() &&
          tag.value.toLowerCase() === parsedNew.value.toLowerCase(),
      )
    : undefined;

  const handleSelect = (tag: Tag) => {
    onChange([...value, tag]);
    setQuery("");
  };

  const handleRemove = (tag: Tag) => {
    onChange(value.filter((v) => v.id !== tag.id));
  };

  const handleCreate = async () => {
    if (!parsedNew || exactMatch) return;
    const created = await createMut.mutateAsync({
      key: parsedNew.key,
      value: parsedNew.value,
    });
    onChange([...value, created]);
    setQuery("");
  };

  return (
    <div className="space-y-2" data-testid="tag-picker">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {value.map((tag) => (
            <TagChip
              key={tag.id}
              tag={tag}
              onRemove={() => handleRemove(tag)}
            />
          ))}
        </div>
      )}
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            // Defer so clicks on dropdown items register.
            window.setTimeout(() => setOpen(false), 120);
          }}
          placeholder={placeholder ?? t("tags.picker.placeholder")}
          className="w-full rounded border border-rule px-2 py-1 text-sm"
          aria-label={t("tags.picker.label")}
        />
        {open && (matches.length > 0 || (allowCreate && parsedNew && !exactMatch)) && (
          <ul
            role="listbox"
            className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded border border-rule bg-paper-raised shadow-lg"
          >
            {matches.map((tag) => (
              <li key={tag.id}>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => handleSelect(tag)}
                  className="flex w-full items-center gap-2 px-2 py-1 text-left text-sm hover:bg-paper-sunk"
                >
                  <TagChip tag={tag} />
                </button>
              </li>
            ))}
            {allowCreate && parsedNew && !exactMatch && (
              <li className="border-t border-rule">
                <button
                  type="button"
                  disabled={createMut.isPending}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => void handleCreate()}
                  className="w-full px-2 py-1 text-left text-sm text-ink-muted hover:bg-paper-sunk disabled:opacity-50"
                >
                  {t("tags.picker.create", {
                    key: parsedNew.key,
                    value: parsedNew.value,
                  })}
                </button>
              </li>
            )}
          </ul>
        )}
      </div>
      {allowCreate && (
        <p className="text-xs text-ink-muted">{t("tags.picker.hint")}</p>
      )}
    </div>
  );
}
