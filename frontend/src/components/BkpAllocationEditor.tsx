/**
 * Editor for multi-BKP allocations on a cost item (Phase 11A).
 *
 * Each row binds a BKP code to a permille share; the sum must equal
 * 1000‰. Mirrors {@link AllocationEditor} (per-unit allocations) so the
 * two editors look familiar side-by-side. The component is purely
 * controlled — validation is best-effort here and authoritative on the
 * server.
 */
import { useTranslation } from "react-i18next";
import type { BkpAllocationItem } from "@/features/costs/types";
import type { BkpCode } from "@/features/costs/types";

export interface BkpAllocationEditorProps {
  value: BkpAllocationItem[];
  onChange: (next: BkpAllocationItem[]) => void;
  bkpCodes: BkpCode[];
  readonly?: boolean;
}

const TOTAL_PERMILLE = 1000;

export function BkpAllocationEditor({
  value,
  onChange,
  bkpCodes,
  readonly,
}: BkpAllocationEditorProps): JSX.Element {
  const { t } = useTranslation();
  const codesByCode = new Map(bkpCodes.map((c) => [c.code, c]));
  const allocatedCodes = new Set(value.map((a) => a.bkp_code));
  const availableCodes = bkpCodes.filter((c) => !allocatedCodes.has(c.code));
  const sum = value.reduce((acc, a) => acc + (a.share_permille || 0), 0);
  const balanced = sum === TOTAL_PERMILLE;

  const updateShare = (bkpCode: string, share: number) => {
    const clamped = Math.max(0, Math.min(TOTAL_PERMILLE, share || 0));
    onChange(
      value.map((a) =>
        a.bkp_code === bkpCode ? { ...a, share_permille: clamped } : a,
      ),
    );
  };

  const addCode = (code: string) => {
    if (!code || allocatedCodes.has(code)) return;
    onChange([...value, { bkp_code: code, share_permille: 0 }]);
  };

  const removeCode = (code: string) => {
    onChange(value.filter((a) => a.bkp_code !== code));
  };

  return (
    <div data-testid="bkp-allocation-editor">
      <h4 className="mb-2 text-sm font-medium">
        {t("costs.bkpAllocations.title")}
      </h4>
      {value.length === 0 && (
        <p className="mb-2 text-sm text-slate-500">
          {t("costs.bkpAllocations.empty")}
        </p>
      )}
      {value.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-500">
            <tr>
              <th className="py-1">{t("costs.bkpAllocations.codeColumn")}</th>
              <th className="py-1">{t("costs.bkpAllocations.shareColumn")}</th>
              {!readonly && <th />}
            </tr>
          </thead>
          <tbody>
            {value.map((a) => {
              const code = codesByCode.get(a.bkp_code);
              return (
                <tr key={a.bkp_code} className="border-t border-slate-200">
                  <td className="py-1 font-mono text-xs">
                    {a.bkp_code}
                    {code && (
                      <span className="ml-2 font-sans text-slate-500">
                        {code.label_de}
                      </span>
                    )}
                  </td>
                  <td className="py-1">
                    <input
                      type="number"
                      min={0}
                      max={1000}
                      value={a.share_permille}
                      disabled={readonly}
                      onChange={(e) =>
                        updateShare(a.bkp_code, Number(e.target.value))
                      }
                      className="w-24 rounded border border-slate-300 px-2 py-1"
                      aria-label={`${t("costs.bkpAllocations.shareColumn")} ${a.bkp_code}`}
                    />
                    <span className="ml-1 text-slate-500">‰</span>
                  </td>
                  {!readonly && (
                    <td className="py-1 text-right">
                      <button
                        type="button"
                        onClick={() => removeCode(a.bkp_code)}
                        className="text-xs text-red-700 hover:underline"
                      >
                        {t("costs.bkpAllocations.remove")}
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {!readonly && availableCodes.length > 0 && (
        <div className="mt-2">
          <select
            value=""
            onChange={(e) => {
              addCode(e.target.value);
              e.target.value = "";
            }}
            aria-label={t("costs.bkpAllocations.add")}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="">{t("costs.bkpAllocations.chooseCode")}</option>
            {availableCodes.map((c) => (
              <option key={c.code} value={c.code}>
                {c.code} — {c.label_de}
              </option>
            ))}
          </select>
        </div>
      )}

      <p
        role="status"
        aria-live="polite"
        className={`mt-3 text-sm font-medium ${
          balanced ? "text-green-700" : "text-red-700"
        }`}
      >
        {t("costs.bkpAllocations.sum", { sum })}
        {!balanced && " — " + t("costs.bkpAllocations.sumHint")}
      </p>
    </div>
  );
}
