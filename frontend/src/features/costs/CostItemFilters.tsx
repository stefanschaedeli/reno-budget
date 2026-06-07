import { useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import type { Unit } from "@/features/objects/types";
import { TagPicker } from "@/components/TagPicker";
import { useLots } from "@/features/lots/api";
import { useProjects } from "@/features/projects/api";
import { useTags } from "@/features/tags/api";
import type { Tag } from "@/features/tags/types";
import {
  COST_PRIORITIES,
  COST_STATUSES,
  type CostItemFilters as Filters,
  type CostPriority,
  type CostStatus,
} from "./types";

/**
 * Filter bar for the cost-items page.
 *
 * State lives in the URL search params so views are linkable / refresh-
 * safe and back-button navigation restores the user's filter set. The
 * parsed {@link Filters} is exposed via `onChange` for the data hook
 * whenever the URL changes.
 */
export interface CostItemFiltersProps {
  units: Unit[];
  objectId: string;
  onChange: (filters: Filters) => void;
}

const STATUS_PARAM = "status";
const PRIORITY_PARAM = "priority";
const YEAR_PARAM = "year";
const UNIT_PARAM = "unit";
const BKP_PARAM = "bkp";
const PROJECT_PARAM = "project";
const TAG_PARAM = "tag";
const LOT_PARAM = "lot";
const Q_PARAM = "q";

export function parseFiltersFromParams(params: URLSearchParams): Filters {
  const statuses = params
    .getAll(STATUS_PARAM)
    .filter((s): s is CostStatus =>
      (COST_STATUSES as readonly string[]).includes(s),
    );
  const priorities = params
    .getAll(PRIORITY_PARAM)
    .filter((p): p is CostPriority =>
      (COST_PRIORITIES as readonly string[]).includes(p),
    );
  const yearRaw = params.get(YEAR_PARAM);
  const year = yearRaw && /^\d+$/.test(yearRaw) ? Number(yearRaw) : null;
  const tagIds = params.getAll(TAG_PARAM).filter((v) => v.length > 0);
  return {
    status: statuses.length > 0 ? statuses : undefined,
    priority: priorities.length > 0 ? priorities : undefined,
    planned_year: year,
    unit_id: params.get(UNIT_PARAM) || null,
    bkp_prefix: params.get(BKP_PARAM) || null,
    project_id: params.get(PROJECT_PARAM) || null,
    tag_ids: tagIds.length > 0 ? tagIds : undefined,
    lot_id: params.get(LOT_PARAM) || null,
    q: params.get(Q_PARAM) || null,
  };
}

export function CostItemFilters({
  units,
  objectId,
  onChange,
}: CostItemFiltersProps): JSX.Element {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const projectsQuery = useProjects(objectId);
  const lotsQuery = useLots(objectId);
  const tagsQuery = useTags(objectId);

  const filters = useMemo(() => parseFiltersFromParams(params), [params]);

  const selectedTags: Tag[] = useMemo(() => {
    const ids = new Set(filters.tag_ids ?? []);
    return (tagsQuery.data ?? []).filter((tag) => ids.has(tag.id));
  }, [filters.tag_ids, tagsQuery.data]);

  // Latest onChange in a ref so we don't re-fire when the parent rebinds it.
  const onChangeRef = useRef(onChange);
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);
  useEffect(() => {
    onChangeRef.current(filters);
  }, [filters]);

  const setMulti = (key: string, values: string[]) => {
    const next = new URLSearchParams(params);
    next.delete(key);
    for (const v of values) next.append(key, v);
    setParams(next, { replace: true });
  };

  const setScalar = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === "") next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };

  const toggleInArray = (
    current: string[] | undefined,
    value: string,
  ): string[] => {
    const set = new Set(current ?? []);
    if (set.has(value)) set.delete(value);
    else set.add(value);
    return Array.from(set);
  };

  const reset = () => setParams(new URLSearchParams(), { replace: true });

  return (
    <section
      aria-label={t("costs.filters.title")}
      className="mb-4 rounded border border-slate-200 bg-slate-50 p-3"
    >
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div>
          <p className="mb-1 text-xs font-medium text-slate-600">
            {t("costs.filters.status")}
          </p>
          <div className="flex flex-wrap gap-1">
            {COST_STATUSES.map((s) => {
              const active = filters.status?.includes(s) ?? false;
              return (
                <button
                  key={s}
                  type="button"
                  aria-pressed={active}
                  onClick={() =>
                    setMulti(STATUS_PARAM, toggleInArray(filters.status, s))
                  }
                  className={`rounded border px-2 py-0.5 text-xs ${
                    active
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-300 bg-white"
                  }`}
                >
                  {t(`costs.status.${s}`)}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <p className="mb-1 text-xs font-medium text-slate-600">
            {t("costs.filters.priority")}
          </p>
          <div className="flex flex-wrap gap-1">
            {COST_PRIORITIES.map((p) => {
              const active = filters.priority?.includes(p) ?? false;
              return (
                <button
                  key={p}
                  type="button"
                  aria-pressed={active}
                  onClick={() =>
                    setMulti(PRIORITY_PARAM, toggleInArray(filters.priority, p))
                  }
                  className={`rounded border px-2 py-0.5 text-xs ${
                    active
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-300 bg-white"
                  }`}
                >
                  {t(`costs.priority.${p}`)}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">
            {t("costs.filters.plannedYear")}
            <input
              type="number"
              min={1900}
              max={2200}
              value={filters.planned_year ?? ""}
              onChange={(e) => setScalar(YEAR_PARAM, e.target.value || null)}
              className="mt-1 w-32 rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">
            {t("costs.filters.unit")}
            <select
              value={filters.unit_id ?? ""}
              onChange={(e) => setScalar(UNIT_PARAM, e.target.value || null)}
              className="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="">{t("costs.filters.anyUnit")}</option>
              {units.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">
            {t("costs.filters.bkpPrefix")}
            <input
              type="text"
              value={filters.bkp_prefix ?? ""}
              onChange={(e) => setScalar(BKP_PARAM, e.target.value || null)}
              placeholder="z. B. C"
              className="mt-1 w-32 rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">
            {t("costs.filters.project")}
            <select
              value={filters.project_id ?? ""}
              onChange={(e) => setScalar(PROJECT_PARAM, e.target.value || null)}
              className="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="">{t("costs.filters.anyProject")}</option>
              {(projectsQuery.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">
            {t("costs.filters.lot")}
            <select
              value={filters.lot_id ?? ""}
              onChange={(e) => setScalar(LOT_PARAM, e.target.value || null)}
              className="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            >
              <option value="">{t("costs.filters.anyLot")}</option>
              {(lotsQuery.data ?? []).map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">
            {t("costs.filters.search")}
            <input
              type="search"
              value={filters.q ?? ""}
              onChange={(e) => setScalar(Q_PARAM, e.target.value || null)}
              className="mt-1 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </label>
        </div>

        <div className="md:col-span-3">
          <p className="mb-1 text-xs font-medium text-slate-600">
            {t("costs.filters.tags")}
          </p>
          <TagPicker
            objectId={objectId}
            value={selectedTags}
            onChange={(next) => setMulti(TAG_PARAM, next.map((tag) => tag.id))}
            allowCreate={false}
          />
        </div>
      </div>

      <div className="mt-3 text-right">
        <button
          type="button"
          onClick={reset}
          className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100"
        >
          {t("costs.filters.reset")}
        </button>
      </div>
    </section>
  );
}
