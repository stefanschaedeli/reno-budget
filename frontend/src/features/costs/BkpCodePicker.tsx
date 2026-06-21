import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useBkpTree } from "@/api/bkp";
import type { BkpTreeNode } from "./types";

/**
 * Hierarchical eBKP-H code picker.
 *
 * Renders a searchable tree (Hauptgruppe → Elementgruppe → …).  When a
 * search term is entered the tree is filtered to nodes whose code OR
 * `label_de` matches; ancestor chains of matching nodes are preserved
 * so context isn't lost.
 *
 * Selection is exposed via the controlled `value` / `onChange` pair so
 * the picker is reusable inside React Hook Form via `Controller` or a
 * plain `<input type="hidden">`.
 */
export interface BkpCodePickerProps {
  value: string | null;
  onChange: (code: string) => void;
  /** Optional label override for the empty-selection display. */
  placeholder?: string;
}

function filterTree(nodes: BkpTreeNode[], query: string): BkpTreeNode[] {
  if (!query) return nodes;
  const q = query.toLowerCase();
  const visit = (node: BkpTreeNode): BkpTreeNode | null => {
    const selfMatch =
      node.code.toLowerCase().includes(q) ||
      node.label_de.toLowerCase().includes(q);
    const children = node.children
      .map((c) => visit(c))
      .filter((c): c is BkpTreeNode => c !== null);
    if (selfMatch || children.length > 0) {
      return { ...node, children };
    }
    return null;
  };
  return nodes.map(visit).filter((n): n is BkpTreeNode => n !== null);
}

function findLabel(nodes: BkpTreeNode[], code: string): string | null {
  for (const node of nodes) {
    if (node.code === code) return node.label_de;
    const child = findLabel(node.children, code);
    if (child) return child;
  }
  return null;
}

interface NodeRowProps {
  node: BkpTreeNode;
  depth: number;
  selected: string | null;
  expandedAll: boolean;
  onSelect: (code: string) => void;
}

function NodeRow({
  node,
  depth,
  selected,
  expandedAll,
  onSelect,
}: NodeRowProps): JSX.Element {
  const [open, setOpen] = useState(depth < 1);
  const isOpen = expandedAll || open;
  const hasChildren = node.children.length > 0;
  const isSelected = node.code === selected;
  return (
    <li>
      <div
        className={`flex items-center gap-1 rounded px-1 py-0.5 ${
          isSelected ? "bg-paper-sunk" : "hover:bg-paper-sunk"
        }`}
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            aria-label={isOpen ? "Zuklappen" : "Aufklappen"}
            onClick={() => setOpen((v) => !v)}
            className="h-4 w-4 text-xs text-ink-muted"
          >
            {isOpen ? "▾" : "▸"}
          </button>
        ) : (
          <span className="inline-block h-4 w-4" />
        )}
        <button
          type="button"
          onClick={() => onSelect(node.code)}
          className="flex-1 text-left text-sm"
        >
          <span className="font-mono text-xs text-ink-muted">{node.code}</span>
          <span className="ml-2">{node.label_de}</span>
        </button>
      </div>
      {hasChildren && isOpen && (
        <ul>
          {node.children.map((child) => (
            <NodeRow
              key={child.code}
              node={child}
              depth={depth + 1}
              selected={selected}
              expandedAll={expandedAll}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export function BkpCodePicker({
  value,
  onChange,
  placeholder,
}: BkpCodePickerProps): JSX.Element {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const { data, isLoading } = useBkpTree();

  const filtered = useMemo(() => filterTree(data ?? [], query), [data, query]);
  const selectedLabel = useMemo(
    () => (value ? findLabel(data ?? [], value) : null),
    [data, value],
  );

  return (
    <div className="rounded border border-rule">
      <div className="border-b border-rule p-2">
        <div className="mb-2 text-xs text-ink-muted">
          {value ? (
            <span>
              <span className="font-mono">{value}</span>
              {selectedLabel ? ` — ${selectedLabel}` : ""}
            </span>
          ) : (
            (placeholder ?? t("costs.bkp.none"))
          )}
        </div>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("costs.bkp.search")}
          aria-label={t("costs.bkp.search")}
          className="w-full rounded border border-rule px-2 py-1 text-sm"
        />
      </div>
      <div className="max-h-64 overflow-auto p-1">
        {isLoading && (
          <p className="p-2 text-sm text-ink-muted">
            {t("costs.bkp.loading")}
          </p>
        )}
        {!isLoading && filtered.length === 0 && (
          <p className="p-2 text-sm text-ink-muted">{t("costs.bkp.empty")}</p>
        )}
        {!isLoading && filtered.length > 0 && (
          <ul role="tree">
            {filtered.map((node) => (
              <NodeRow
                key={node.code}
                node={node}
                depth={0}
                selected={value}
                expandedAll={query.length > 0}
                onSelect={onChange}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
