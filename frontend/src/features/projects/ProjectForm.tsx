/**
 * Create / edit form for a Project. Validation is driven by the Zod
 * schema in `types.ts`; the parent owns the submit mutation.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  PROJECT_STATUSES,
  projectCreateSchema,
  type ProjectCreate,
  type ProjectStatus,
} from "./types";

export interface ProjectFormProps {
  initial?: Partial<ProjectCreate> | undefined;
  onSubmit: (payload: ProjectCreate) => void | Promise<void>;
  onCancel?: (() => void) | undefined;
  submitting?: boolean | undefined;
}

interface FormState {
  name: string;
  description: string;
  status: ProjectStatus;
  planned_year: string;
  rough_estimate_chf: string;
}

export function ProjectForm({
  initial,
  onSubmit,
  onCancel,
  submitting,
}: ProjectFormProps): JSX.Element {
  const { t } = useTranslation();
  const [state, setState] = useState<FormState>(() => ({
    name: initial?.name ?? "",
    description: initial?.description ?? "",
    status: initial?.status ?? "idea",
    planned_year: initial?.planned_year?.toString() ?? "",
    rough_estimate_chf:
      initial?.rough_estimate_chf != null
        ? String(initial.rough_estimate_chf)
        : "",
  }));
  const [errors, setErrors] = useState<Map<string, string>>(() => new Map());

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setState((prev) => ({ ...prev, [key]: value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const candidate = {
      name: state.name,
      description: state.description || null,
      status: state.status,
      planned_year: state.planned_year ? Number(state.planned_year) : null,
      rough_estimate_chf: state.rough_estimate_chf
        ? state.rough_estimate_chf
        : null,
    };
    const result = projectCreateSchema.safeParse(candidate);
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
    void onSubmit(result.data);
  };

  const err = (key: string): string | undefined => errors.get(key);

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <label className="block text-sm">
        <span className="mb-1 block font-medium">
          {t("projects.fields.name")}
        </span>
        <input
          type="text"
          value={state.name}
          onChange={(e) => update("name", e.target.value)}
          className="w-full rounded border border-rule px-2 py-1"
          required
        />
        {err("name") && <p className="text-xs text-negative">{err("name")}</p>}
      </label>

      <label className="block text-sm">
        <span className="mb-1 block font-medium">
          {t("projects.fields.description")}
        </span>
        <textarea
          value={state.description}
          onChange={(e) => update("description", e.target.value)}
          rows={3}
          className="w-full rounded border border-rule px-2 py-1"
        />
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("projects.fields.status")}
          </span>
          <select
            value={state.status}
            onChange={(e) => update("status", e.target.value as ProjectStatus)}
            className="w-full rounded border border-rule px-2 py-1"
          >
            {PROJECT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`projects.status.${s}`)}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("projects.fields.plannedYear")}
          </span>
          <input
            type="number"
            min={1900}
            max={2200}
            value={state.planned_year}
            onChange={(e) => update("planned_year", e.target.value)}
            className="w-full rounded border border-rule px-2 py-1"
          />
        </label>
      </div>

      <label className="block text-sm">
        <span className="mb-1 block font-medium">
          {t("projects.fields.roughEstimate")}
        </span>
        <input
          type="number"
          min={0}
          step="0.01"
          inputMode="decimal"
          value={state.rough_estimate_chf}
          onChange={(e) => update("rough_estimate_chf", e.target.value)}
          placeholder={t("projects.fields.roughEstimatePlaceholder")}
          className="w-full rounded border border-rule px-2 py-1 tabular-nums"
        />
        {err("rough_estimate_chf") && (
          <p className="text-xs text-negative">{err("rough_estimate_chf")}</p>
        )}
      </label>

      <div className="flex justify-end gap-2 pt-2">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-rule px-3 py-1 text-sm hover:bg-paper-sunk"
          >
            {t("costs.cancel")}
          </button>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-ink px-3 py-1 text-sm text-paper hover:bg-ink disabled:opacity-50"
        >
          {submitting ? t("common.submitting") : t("costs.save")}
        </button>
      </div>
    </form>
  );
}
