/**
 * Create / edit form for a Lot. Validation driven by the Zod schema in
 * `types.ts`; the parent owns the submit mutation.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  LOT_STATUSES,
  lotCreateSchema,
  type LotCreate,
  type LotStatus,
} from "./types";

export interface LotFormProps {
  initial?: Partial<LotCreate> | undefined;
  onSubmit: (payload: LotCreate) => void | Promise<void>;
  onCancel?: (() => void) | undefined;
  submitting?: boolean | undefined;
}

interface FormState {
  name: string;
  description: string;
  status: LotStatus;
  tender_deadline: string;
}

export function LotForm({
  initial,
  onSubmit,
  onCancel,
  submitting,
}: LotFormProps): JSX.Element {
  const { t } = useTranslation();
  const [state, setState] = useState<FormState>(() => ({
    name: initial?.name ?? "",
    description: initial?.description ?? "",
    status: initial?.status ?? "draft",
    tender_deadline: initial?.tender_deadline ?? "",
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
      tender_deadline: state.tender_deadline || null,
    };
    const result = lotCreateSchema.safeParse(candidate);
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
        <span className="mb-1 block font-medium">{t("lots.fields.name")}</span>
        <input
          type="text"
          value={state.name}
          onChange={(e) => update("name", e.target.value)}
          className="w-full rounded border border-slate-300 px-2 py-1"
          required
        />
        {err("name") && <p className="text-xs text-red-700">{err("name")}</p>}
      </label>

      <label className="block text-sm">
        <span className="mb-1 block font-medium">
          {t("lots.fields.description")}
        </span>
        <textarea
          value={state.description}
          onChange={(e) => update("description", e.target.value)}
          rows={3}
          className="w-full rounded border border-slate-300 px-2 py-1"
        />
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("lots.fields.status")}
          </span>
          <select
            value={state.status}
            onChange={(e) => update("status", e.target.value as LotStatus)}
            className="w-full rounded border border-slate-300 px-2 py-1"
          >
            {LOT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`lots.status.${s}`)}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium">
            {t("lots.fields.tenderDeadline")}
          </span>
          <input
            type="date"
            value={state.tender_deadline}
            onChange={(e) => update("tender_deadline", e.target.value)}
            className="w-full rounded border border-slate-300 px-2 py-1"
          />
        </label>
      </div>

      <div className="flex justify-end gap-2 pt-2">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
          >
            {t("costs.cancel")}
          </button>
        )}
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {submitting ? t("common.submitting") : t("costs.save")}
        </button>
      </div>
    </form>
  );
}
