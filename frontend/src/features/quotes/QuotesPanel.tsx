/**
 * Quotes panel embedded in the LotDetailPage.
 *
 * Lists the lot's quotes, lets editors add a new one (picking a
 * supplier from the object-scoped dropdown), and triggers the
 * transactional award via a dedicated button. Award is disabled if the
 * lot already has an awarded quote — switching winners would require
 * manual demotion of the current award, which is intentionally not
 * supported in the UI (it requires a second commit and is a rare
 * operation; do it via direct API call).
 */
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { formatChf } from "@/features/costs/types";
import { useSuppliers } from "@/features/suppliers/api";
import { useAwardQuote, useCreateQuote, useLotQuotes } from "./api";
import type { Quote, QuoteCreate, QuoteStatus } from "./types";

interface Props {
  lotId: string;
  objectId: string;
  /** Lot.status — used to lock the award button once awarded. */
  lotStatus: string;
}

export function QuotesPanel({ lotId, objectId, lotStatus }: Props): JSX.Element {
  const { t } = useTranslation();
  const quotesQuery = useLotQuotes(lotId);
  const suppliersQuery = useSuppliers(objectId);
  const createMut = useCreateQuote(lotId);
  const awardMut = useAwardQuote(lotId);
  const [creating, setCreating] = useState(false);

  const quotes = quotesQuery.data ?? [];
  // Memoize the supplier list so its identity is stable across renders;
  // ``data ?? []`` would otherwise create a new [] each render and invalidate
  // every downstream useMemo unnecessarily.
  const suppliers = useMemo(
    () => suppliersQuery.data ?? [],
    [suppliersQuery.data],
  );
  const supplierById = useMemo(
    () => new Map(suppliers.map((s) => [s.id, s])),
    [suppliers],
  );
  const awardedQuote = quotes.find((q) => q.status === "awarded") ?? null;
  const lotAwarded = lotStatus === "awarded";

  const handleAward = async (quoteId: string) => {
    if (!window.confirm(t("quotes.awardConfirm"))) return;
    try {
      await awardMut.mutateAsync(quoteId);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      window.alert(msg);
    }
  };

  const handleCreate = async (payload: QuoteCreate) => {
    await createMut.mutateAsync(payload);
    setCreating(false);
  };

  return (
    <section className="mb-8">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-lg font-medium">{t("quotes.title")}</h3>
        <button
          type="button"
          onClick={() => setCreating((v) => !v)}
          className="rounded border border-slate-300 px-2 py-1 text-sm hover:bg-slate-100"
        >
          {t("quotes.add")}
        </button>
      </div>

      {awardedQuote && (
        <div
          className="mb-3 rounded border border-green-300 bg-green-50 p-3 text-sm"
          data-testid="awarded-banner"
        >
          <strong>{t("quotes.awardedLabel")}:</strong>{" "}
          {supplierById.get(awardedQuote.supplier_id)?.name ?? "?"} —{" "}
          <span className="tabular-nums">
            {formatChf(awardedQuote.amount_chf)}
          </span>
        </div>
      )}

      {creating && (
        <div className="mb-3 rounded border border-slate-200 bg-slate-50 p-3">
          <QuoteForm
            suppliers={suppliers}
            onSubmit={handleCreate}
            onCancel={() => setCreating(false)}
            submitting={createMut.isPending}
          />
        </div>
      )}

      {quotesQuery.isLoading && (
        <p className="text-slate-500">{t("common.loading")}</p>
      )}
      {quotes.length === 0 && !quotesQuery.isLoading && (
        <p className="text-slate-500">{t("quotes.empty")}</p>
      )}
      {quotes.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
              <th className="px-2 py-2">{t("quotes.fields.supplier")}</th>
              <th className="px-2 py-2 text-right">
                {t("quotes.fields.amount")}
              </th>
              <th className="px-2 py-2">{t("quotes.fields.receivedAt")}</th>
              <th className="px-2 py-2">{t("quotes.fields.status")}</th>
              <th className="px-2 py-2">{t("quotes.fields.validUntil")}</th>
              <th className="px-2 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {quotes.map((q: Quote) => (
              <tr
                key={q.id}
                data-testid={`quote-row-${q.id}`}
                className="border-b border-slate-200"
              >
                <td className="px-2 py-2 font-medium">
                  {supplierById.get(q.supplier_id)?.name ?? "?"}
                </td>
                <td className="px-2 py-2 text-right tabular-nums">
                  {formatChf(q.amount_chf)}
                </td>
                <td className="px-2 py-2">
                  {new Date(q.received_at).toLocaleDateString("de-CH")}
                </td>
                <td className="px-2 py-2">
                  {t(`quotes.status.${q.status}`)}
                </td>
                <td className="px-2 py-2">
                  {q.valid_until
                    ? new Date(q.valid_until).toLocaleDateString("de-CH")
                    : "—"}
                </td>
                <td className="px-2 py-2 text-right">
                  {q.status !== "awarded" && !lotAwarded && (
                    <button
                      type="button"
                      onClick={() => void handleAward(q.id)}
                      disabled={awardMut.isPending}
                      className="rounded border border-green-300 px-2 py-0.5 text-xs text-green-700 hover:bg-green-50 disabled:opacity-60"
                    >
                      {t("quotes.award")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

interface FormProps {
  suppliers: { id: string; name: string }[];
  onSubmit: (payload: QuoteCreate) => Promise<void> | void;
  onCancel: () => void;
  submitting?: boolean;
}

function QuoteForm({
  suppliers,
  onSubmit,
  onCancel,
  submitting,
}: FormProps): JSX.Element {
  const { t } = useTranslation();
  const [supplierId, setSupplierId] = useState(suppliers[0]?.id ?? "");
  const [amount, setAmount] = useState("");
  const [receivedAt, setReceivedAt] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [validUntil, setValidUntil] = useState("");
  const [status, setStatus] = useState<QuoteStatus>("received");
  const [notes, setNotes] = useState("");

  const submit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!supplierId) return;
    void onSubmit({
      supplier_id: supplierId,
      amount_chf: amount,
      received_at: receivedAt,
      valid_until: validUntil === "" ? null : validUntil,
      notes: notes === "" ? null : notes,
      status,
    });
  };

  return (
    <form onSubmit={submit} className="space-y-2 text-sm">
      <div className="grid grid-cols-2 gap-2">
        <label className="block">
          <span className="block text-slate-700">
            {t("quotes.fields.supplier")}
          </span>
          <select
            value={supplierId}
            onChange={(e) => setSupplierId(e.target.value)}
            required
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
          >
            {suppliers.length === 0 && <option value="">—</option>}
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="block text-slate-700">
            {t("quotes.fields.amount")}
          </span>
          <input
            type="text"
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
            placeholder="12345.00"
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
          />
        </label>
        <label className="block">
          <span className="block text-slate-700">
            {t("quotes.fields.receivedAt")}
          </span>
          <input
            type="date"
            value={receivedAt}
            onChange={(e) => setReceivedAt(e.target.value)}
            required
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
          />
        </label>
        <label className="block">
          <span className="block text-slate-700">
            {t("quotes.fields.validUntil")}
          </span>
          <input
            type="date"
            value={validUntil}
            onChange={(e) => setValidUntil(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
          />
        </label>
        <label className="block">
          <span className="block text-slate-700">
            {t("quotes.fields.status")}
          </span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as QuoteStatus)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
          >
            <option value="received">{t("quotes.status.received")}</option>
            <option value="shortlisted">
              {t("quotes.status.shortlisted")}
            </option>
            <option value="rejected">{t("quotes.status.rejected")}</option>
          </select>
        </label>
        <label className="block">
          <span className="block text-slate-700">
            {t("quotes.fields.notes")}
          </span>
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
          />
        </label>
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting || suppliers.length === 0}
          className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700 disabled:opacity-60"
        >
          {submitting ? t("common.submitting") : t("costs.save")}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
        >
          {t("costs.cancel")}
        </button>
      </div>
    </form>
  );
}
