import type { ChangeEvent } from "react";
import { useTranslation } from "react-i18next";
import type { UnitInput } from "./types";

/**
 * Pure, controlled unit-list editor with a live ‰ sum readout.
 *
 * The submit button in the parent form is responsible for invoking the
 * Zod schema for the final validity check; this component only renders
 * the inline sum so the user gets immediate feedback while typing.
 */
export interface UnitEditorProps {
  units: UnitInput[];
  onChange: (next: UnitInput[]) => void;
  readonly?: boolean;
}

const TOTAL_PERMILLE = 1000;

export function UnitEditor({ units, onChange, readonly }: UnitEditorProps): JSX.Element {
  const { t } = useTranslation();
  const sum = units.reduce((acc, u) => acc + (Number(u.wertquote_permille) || 0), 0);
  const balanced = sum === TOTAL_PERMILLE;

  const update = (index: number, patch: Partial<UnitInput>) => {
    onChange(units.map((u, i) => (i === index ? { ...u, ...patch } : u)));
  };

  const remove = (index: number) => onChange(units.filter((_, i) => i !== index));
  const add = () =>
    onChange([...units, { label: "", wertquote_permille: 0, area_m2: null }]);

  return (
    <div>
      <table className="w-full text-sm">
        <thead className="text-left text-slate-500">
          <tr>
            <th className="py-1">{t("objects.units.label")}</th>
            <th className="py-1">{t("objects.units.wertquote")}</th>
            <th className="py-1">{t("objects.units.area")}</th>
            {!readonly && <th />}
          </tr>
        </thead>
        <tbody>
          {units.map((u, idx) => (
            <tr key={idx} className="border-t border-slate-200">
              <td className="py-1">
                <input
                  type="text"
                  value={u.label}
                  disabled={readonly}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    update(idx, { label: e.target.value })
                  }
                  className="w-full rounded border border-slate-300 px-2 py-1"
                  aria-label={t("objects.units.label")}
                />
              </td>
              <td className="py-1">
                <input
                  type="number"
                  min={0}
                  max={1000}
                  value={u.wertquote_permille}
                  disabled={readonly}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    update(idx, {
                      wertquote_permille: Math.max(
                        0,
                        Math.min(1000, Number(e.target.value) || 0),
                      ),
                    })
                  }
                  className="w-24 rounded border border-slate-300 px-2 py-1"
                  aria-label={t("objects.units.wertquote")}
                />
                <span className="ml-1 text-slate-500">‰</span>
              </td>
              <td className="py-1">
                <input
                  type="number"
                  min={0}
                  value={u.area_m2 ?? ""}
                  disabled={readonly}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    update(idx, {
                      area_m2: e.target.value === "" ? null : Number(e.target.value),
                    })
                  }
                  className="w-24 rounded border border-slate-300 px-2 py-1"
                  aria-label={t("objects.units.area")}
                />
                <span className="ml-1 text-slate-500">m²</span>
              </td>
              {!readonly && (
                <td className="py-1 text-right">
                  <button
                    type="button"
                    onClick={() => remove(idx)}
                    className="text-xs text-red-700 hover:underline"
                    disabled={units.length <= 1}
                  >
                    {t("objects.units.remove")}
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-3 flex items-center justify-between">
        {!readonly && (
          <button
            type="button"
            onClick={add}
            className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100"
          >
            {t("objects.units.add")}
          </button>
        )}
        <p
          role="status"
          aria-live="polite"
          className={`text-sm font-medium ${balanced ? "text-green-700" : "text-red-700"}`}
        >
          {t("objects.units.sum", { sum })}
          {!balanced && " — " + t("objects.units.sumHint")}
        </p>
      </div>
    </div>
  );
}
