import { useTranslation } from "react-i18next";
import type { Unit } from "@/features/objects/types";
import type { CostItemAllocation, CostScope } from "./types";

/**
 * Controlled editor for per-cost-item allocations (CostItemUnitAllocation).
 *
 * Enforces the **sum = 1000‰** invariant matching the backend's
 * `services/allocations.py` validator. Sum violations are surfaced as
 * a visual warning only — the parent form's Zod schema produces the
 * blocking error and the server remains authoritative.
 *
 * Behaviour by {@link CostScope}:
 *  - `shared`: every object unit appears as a row by default with its
 *    Wertquote share. The user may override individual values. The
 *    "Standard (Wertquote)" button resets all rows to the Wertquote
 *    distribution.
 *  - `unit`: starts empty. The user adds rows by picking units from a
 *    dropdown of units not yet allocated.
 */
export interface AllocationEditorProps {
  scope: CostScope;
  units: Unit[];
  value: CostItemAllocation[];
  onChange: (next: CostItemAllocation[]) => void;
  readonly?: boolean;
}

const TOTAL_PERMILLE = 1000;

function wertquoteDefaults(units: Unit[]): CostItemAllocation[] {
  return units.map((u) => ({
    unit_id: u.id,
    share_permille: u.wertquote_permille,
  }));
}

export function AllocationEditor({
  scope,
  units,
  value,
  onChange,
  readonly,
}: AllocationEditorProps): JSX.Element {
  const { t } = useTranslation();
  const unitsById = new Map(units.map((u) => [u.id, u]));
  const allocatedIds = new Set(value.map((a) => a.unit_id));
  const availableUnits = units.filter((u) => !allocatedIds.has(u.id));
  const sum = value.reduce((acc, a) => acc + (a.share_permille || 0), 0);
  const balanced = sum === TOTAL_PERMILLE;

  const updateShare = (unitId: string, share: number) => {
    const clamped = Math.max(0, Math.min(TOTAL_PERMILLE, share || 0));
    onChange(
      value.map((a) =>
        a.unit_id === unitId ? { ...a, share_permille: clamped } : a,
      ),
    );
  };

  const addUnit = (unitId: string) => {
    if (!unitId || allocatedIds.has(unitId)) return;
    onChange([...value, { unit_id: unitId, share_permille: 0 }]);
  };

  const removeUnit = (unitId: string) => {
    onChange(value.filter((a) => a.unit_id !== unitId));
  };

  const resetToWertquote = () => {
    onChange(wertquoteDefaults(units));
  };

  const showEmptyShared = scope === "shared" && value.length === 0;
  const showEmptyUnit = scope === "unit" && value.length === 0;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-medium">{t("costs.fields.allocations")}</h4>
        {!readonly && units.length > 0 && (
          <button
            type="button"
            onClick={resetToWertquote}
            title={t("costs.allocations.resetHint")}
            className="rounded border border-rule px-2 py-1 text-xs hover:bg-paper-sunk"
          >
            {t("costs.allocations.reset")}
          </button>
        )}
      </div>

      {showEmptyShared && units.length === 0 && (
        <p className="text-sm text-ink-muted">
          {t("costs.allocations.emptyShared")}
        </p>
      )}
      {showEmptyUnit && (
        <p className="mb-2 text-sm text-ink-muted">
          {t("costs.allocations.emptyUnit")}
        </p>
      )}

      {value.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-ink-muted">
            <tr>
              <th className="py-1">{t("costs.allocations.unitColumn")}</th>
              <th className="py-1">{t("costs.allocations.shareColumn")}</th>
              {!readonly && <th />}
            </tr>
          </thead>
          <tbody>
            {value.map((a) => {
              const unit = unitsById.get(a.unit_id);
              return (
                <tr key={a.unit_id} className="border-t border-rule">
                  <td className="py-1">{unit?.label ?? a.unit_id}</td>
                  <td className="py-1">
                    <input
                      type="number"
                      min={0}
                      max={1000}
                      value={a.share_permille}
                      disabled={readonly}
                      onChange={(e) =>
                        updateShare(a.unit_id, Number(e.target.value))
                      }
                      className="w-24 rounded border border-rule px-2 py-1"
                      aria-label={`${t("costs.allocations.shareColumn")} ${unit?.label ?? ""}`}
                    />
                    <span className="ml-1 text-ink-muted">‰</span>
                  </td>
                  {!readonly && (
                    <td className="py-1 text-right">
                      <button
                        type="button"
                        onClick={() => removeUnit(a.unit_id)}
                        className="text-xs text-negative hover:underline"
                      >
                        {t("costs.allocations.remove")}
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {!readonly && availableUnits.length > 0 && (
        <div className="mt-2">
          <select
            value=""
            onChange={(e) => {
              addUnit(e.target.value);
              e.target.value = "";
            }}
            aria-label={t("costs.allocations.add")}
            className="rounded border border-rule px-2 py-1 text-sm"
          >
            <option value="">{t("costs.allocations.chooseUnit")}</option>
            {availableUnits.map((u) => (
              <option key={u.id} value={u.id}>
                {u.label}
              </option>
            ))}
          </select>
        </div>
      )}

      <p
        role="status"
        aria-live="polite"
        className={`mt-3 text-sm font-medium ${
          balanced ? "text-positive" : "text-negative"
        }`}
      >
        {t("costs.allocations.sum", { sum })}
        {!balanced && " — " + t("costs.allocations.sumHint")}
      </p>
    </div>
  );
}

/** Exposed for tests + initial-state construction outside this module. */
export { wertquoteDefaults };
