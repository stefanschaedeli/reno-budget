import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { Unit } from "@/features/objects/types";
import { useBkpCodes } from "@/api/bkp";
import { useProjects } from "@/features/projects/api";
import { BkpAllocationEditor } from "@/components/BkpAllocationEditor";
import { TagPicker } from "@/components/TagPicker";
import {
  useAssignTag,
  useTagsForTarget,
  useUnassignTag,
} from "@/features/tags/api";
import type { Tag } from "@/features/tags/types";
import { AllocationEditor, wertquoteDefaults } from "./AllocationEditor";
import { BkpCodePicker } from "./BkpCodePicker";
import {
  COST_PRIORITIES,
  COST_STATUSES,
  type BkpAllocationItem,
  type CostItemAllocation,
  type CostItemInput,
  type CostPriority,
  type CostScope,
  type CostStatus,
  costItemInputSchema,
} from "./types";

/**
 * Create / edit form for a single CostItem.
 *
 * Validation is driven by the Zod schema in `types.ts` — the same shape
 * the backend Pydantic schema validates against, so error messages can
 * round-trip. Monetary inputs are accepted as decimal strings (e.g.
 * "12345.67") and submitted unchanged; we never coerce to JS number.
 *
 * The component is intentionally headless wrt. submit transport — the
 * parent owns the mutation and gets the validated payload via
 * `onSubmit`. That keeps create/edit indistinguishable here.
 */
export interface CostItemFormProps {
  units: Unit[];
  objectId: string;
  /** Existing cost-item id when editing; enables tag assignment persistence. */
  costItemId?: string | undefined;
  initial?: Partial<CostItemInput> | undefined;
  /**
   * Submit handler. For NEW items the form has no cost-item id to persist tag
   * assignments against, so the selected tags are returned via ``pendingTags``
   * so the parent can call ``assignTag(...)`` after the create resolves. For
   * EDIT items tag changes are persisted immediately inside the form and
   * ``pendingTags`` will be an empty list.
   */
  onSubmit: (
    payload: CostItemInput,
    pendingTags: Tag[],
  ) => void | Promise<void>;
  onCancel?: (() => void) | undefined;
  submitting?: boolean | undefined;
}

interface FormState {
  bkp_code: string;
  project_id: string;
  npk_code: string;
  title: string;
  description: string;
  status: CostStatus;
  priority: CostPriority;
  planned_year: string;
  planned_amount_chf: string;
  actual_amount_chf: string;
  actual_date: string;
  lifespan_years: string;
  warranty_until: string;
  scope: CostScope;
  allocations: CostItemAllocation[];
  bkp_allocations: BkpAllocationItem[];
  /** When true, the single bkp_code picker is hidden and bkp_allocations is used. */
  detailedBkp: boolean;
}

function emptyState(units: Unit[], initial?: Partial<CostItemInput>): FormState {
  const bkpAllocs = initial?.bkp_allocations ?? [];
  return {
    bkp_code: initial?.bkp_code ?? "",
    project_id: initial?.project_id ?? "",
    npk_code: initial?.npk_code ?? "",
    title: initial?.title ?? "",
    description: initial?.description ?? "",
    status: initial?.status ?? "idea",
    priority: initial?.priority ?? "med",
    planned_year: initial?.planned_year?.toString() ?? "",
    planned_amount_chf: initial?.planned_amount_chf ?? "",
    actual_amount_chf: initial?.actual_amount_chf ?? "",
    actual_date: initial?.actual_date ?? "",
    lifespan_years: initial?.lifespan_years?.toString() ?? "",
    warranty_until: initial?.warranty_until ?? "",
    scope: initial?.scope ?? "shared",
    allocations:
      initial?.allocations ??
      (initial?.scope === "unit" ? [] : wertquoteDefaults(units)),
    bkp_allocations: bkpAllocs,
    detailedBkp: bkpAllocs.length > 0,
  };
}

function stateToPayload(s: FormState): unknown {
  return {
    // When using detailed multi-BKP, the singleton must be null per the
    // backend XOR rule.
    bkp_code: s.detailedBkp ? null : s.bkp_code || null,
    project_id: s.project_id || null,
    npk_code: s.npk_code || null,
    title: s.title,
    description: s.description || null,
    status: s.status,
    priority: s.priority,
    planned_year: s.planned_year ? Number(s.planned_year) : null,
    planned_amount_chf: s.planned_amount_chf || null,
    actual_amount_chf: s.actual_amount_chf || null,
    actual_date: s.actual_date || null,
    lifespan_years: s.lifespan_years ? Number(s.lifespan_years) : null,
    warranty_until: s.warranty_until || null,
    scope: s.scope,
    allocations: s.allocations,
    bkp_allocations: s.detailedBkp ? s.bkp_allocations : [],
  };
}

export function CostItemForm({
  units,
  objectId,
  costItemId,
  initial,
  onSubmit,
  onCancel,
  submitting,
}: CostItemFormProps): JSX.Element {
  const { t } = useTranslation();
  const [state, setState] = useState<FormState>(() =>
    emptyState(units, initial),
  );
  const [errors, setErrors] = useState<Map<string, string>>(() => new Map());

  const projectsQuery = useProjects(objectId);
  const bkpCodesQuery = useBkpCodes();
  const tagsQuery = useTagsForTarget(
    "cost_item",
    costItemId ?? "",
  );
  const assignTagMut = useAssignTag();
  const unassignTagMut = useUnassignTag();
  // For new items, tag selections live in local state until parent commits.
  const [pendingTags, setPendingTags] = useState<Tag[]>([]);

  const selectedTags = costItemId ? (tagsQuery.data ?? []) : pendingTags;

  const handleTagsChange = (next: Tag[]) => {
    if (!costItemId) {
      // Cannot persist until the cost item exists; the parent receives this
      // list via ``onSubmit(payload, pendingTags)`` and runs assignTag for
      // each id after the create mutation resolves.
      setPendingTags(next);
      return;
    }
    const current = new Set(selectedTags.map((t) => t.id));
    const nextIds = new Set(next.map((t) => t.id));
    for (const tag of next) {
      if (!current.has(tag.id)) {
        void assignTagMut.mutateAsync({
          tagId: tag.id,
          targetType: "cost_item",
          targetId: costItemId,
        });
      }
    }
    for (const tag of selectedTags) {
      if (!nextIds.has(tag.id)) {
        void unassignTagMut.mutateAsync({
          tagId: tag.id,
          targetType: "cost_item",
          targetId: costItemId,
        });
      }
    }
  };

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setState((prev) => ({ ...prev, [key]: value }));

  const setScope = (scope: CostScope) => {
    setState((prev) => ({
      ...prev,
      scope,
      allocations:
        scope === "shared" && prev.allocations.length === 0
          ? wertquoteDefaults(units)
          : prev.allocations,
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const candidate = stateToPayload(state);
    const result = costItemInputSchema.safeParse(candidate);
    if (!result.success) {
      const next = new Map<string, string>();
      for (const issue of result.error.issues) {
        const path = issue.path.join(".");
        if (!next.has(path)) next.set(path, issue.message);
      }
      setErrors(next);
      return;
    }
    setErrors(new Map());
    // For new items, hand the locally-selected tags up so the parent can
    // assign them to the freshly-created id. For edits, tag changes already
    // persisted inline via useAssignTag/useUnassignTag — pass [] to be safe.
    void onSubmit(result.data, costItemId ? [] : pendingTags);
  };

  const err = (key: string): string | undefined => errors.get(key);

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("costs.fields.title")}
          </span>
          <input
            type="text"
            value={state.title}
            onChange={(e) => update("title", e.target.value)}
            className="w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none"
            required
          />
        </label>
        {err("title") && <p className="text-xs text-negative">{err("title")}</p>}
      </div>

      <div>
        <label className="mb-1 inline-flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={state.detailedBkp}
            onChange={(e) => update("detailedBkp", e.target.checked)}
          />
          {t("costs.bkpAllocations.toggle")}
        </label>
        <p className="mb-2 text-xs text-ink-muted">
          {t("costs.bkpAllocations.toggleHint")}
        </p>
        {!state.detailedBkp ? (
          <>
            <p className="mb-1 text-sm font-medium">{t("costs.fields.bkp")}</p>
            <BkpCodePicker
              value={state.bkp_code || null}
              onChange={(code) => update("bkp_code", code ?? "")}
            />
            {err("bkp_code") && (
              <p className="text-xs text-negative">{err("bkp_code")}</p>
            )}
          </>
        ) : (
          <BkpAllocationEditor
            value={state.bkp_allocations}
            onChange={(next) => update("bkp_allocations", next)}
            bkpCodes={bkpCodesQuery.data ?? []}
          />
        )}
        {err("bkp_allocations") && (
          <p className="text-xs text-negative">{err("bkp_allocations")}</p>
        )}
      </div>

      <label className="block text-sm">
        <span className="mb-1 block font-medium">{t("costs.project")}</span>
        <select
          value={state.project_id}
          onChange={(e) => update("project_id", e.target.value)}
          className="w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none"
        >
          <option value="">{t("costs.projectNone")}</option>
          {(projectsQuery.data ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>

      <div>
        <p className="mb-1 text-sm font-medium">{t("costs.tags")}</p>
        <TagPicker
          objectId={objectId}
          value={selectedTags}
          onChange={handleTagsChange}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("costs.fields.status")}
          </span>
          <select
            value={state.status}
            onChange={(e) => update("status", e.target.value as CostStatus)}
            className="w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none"
          >
            {COST_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`costs.status.${s}`)}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("costs.fields.priority")}
          </span>
          <select
            value={state.priority}
            onChange={(e) => update("priority", e.target.value as CostPriority)}
            className="w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none"
          >
            {COST_PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {t(`costs.priority.${p}`)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("costs.fields.plannedYear")}
          </span>
          <input
            type="number"
            min={1900}
            max={2200}
            value={state.planned_year}
            onChange={(e) => update("planned_year", e.target.value)}
            className="w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none"
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("costs.fields.lifespanYears")}
          </span>
          <input
            type="number"
            min={0}
            value={state.lifespan_years}
            onChange={(e) => update("lifespan_years", e.target.value)}
            className="w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none"
          />
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("costs.fields.plannedAmount")}
          </span>
          <input
            type="text"
            inputMode="decimal"
            value={state.planned_amount_chf}
            onChange={(e) => update("planned_amount_chf", e.target.value)}
            placeholder="0.00"
            className="w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none"
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("costs.fields.actualAmount")}
          </span>
          <input
            type="text"
            inputMode="decimal"
            value={state.actual_amount_chf}
            onChange={(e) => update("actual_amount_chf", e.target.value)}
            placeholder="0.00"
            className="w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none"
          />
        </label>
      </div>
      {(err("planned_amount_chf") || err("actual_amount_chf")) && (
        <p className="text-xs text-negative">
          {err("planned_amount_chf") ?? err("actual_amount_chf")}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("costs.fields.actualDate")}
          </span>
          <input
            type="date"
            value={state.actual_date}
            onChange={(e) => update("actual_date", e.target.value)}
            className="w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none"
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("costs.fields.warrantyUntil")}
          </span>
          <input
            type="date"
            value={state.warranty_until}
            onChange={(e) => update("warranty_until", e.target.value)}
            className="w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none"
          />
        </label>
      </div>

      <label className="block text-sm">
        <span className="mb-1 block font-medium">
          {t("costs.fields.description")}
        </span>
        <textarea
          value={state.description}
          onChange={(e) => update("description", e.target.value)}
          rows={3}
          className="w-full rounded-sheet border border-rule bg-paper-raised px-2 py-1.5 text-ink focus:border-accent focus:outline-none"
        />
      </label>

      <fieldset>
        <legend className="mb-1 text-sm font-medium">
          {t("costs.fields.scope")}
        </legend>
        <label className="mr-4 text-sm">
          <input
            type="radio"
            name="scope"
            value="shared"
            checked={state.scope === "shared"}
            onChange={() => setScope("shared")}
            className="mr-1"
          />
          {t("costs.scope.shared")}
        </label>
        <label className="text-sm">
          <input
            type="radio"
            name="scope"
            value="unit"
            checked={state.scope === "unit"}
            onChange={() => setScope("unit")}
            className="mr-1"
          />
          {t("costs.scope.unit")}
        </label>
      </fieldset>

      <AllocationEditor
        scope={state.scope}
        units={units}
        value={state.allocations}
        onChange={(next) => update("allocations", next)}
      />
      {err("allocations") && (
        <p className="text-xs text-negative">{err("allocations")}</p>
      )}

      <div className="flex justify-end gap-2 pt-2">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-sheet border border-rule px-3 py-1.5 text-sm text-ink-muted hover:border-ink/30 hover:text-ink"
          >
            {t("costs.cancel")}
          </button>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="rounded-sheet bg-ink px-3 py-1.5 text-sm text-paper hover:bg-ink/85 disabled:opacity-50"
        >
          {submitting ? t("common.submitting") : t("costs.save")}
        </button>
      </div>
    </form>
  );
}
