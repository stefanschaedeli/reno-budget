/**
 * Reusable create/update form for a Supplier.
 *
 * Used both inline on the SuppliersPage drawer and on the
 * SupplierDetailPage edit panel.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { SupplierCreate } from "./types";

interface Props {
  initial?: Partial<SupplierCreate>;
  onSubmit: (payload: SupplierCreate) => Promise<void> | void;
  onCancel?: () => void;
  submitting?: boolean;
}

export function SupplierForm({
  initial,
  onSubmit,
  onCancel,
  submitting,
}: Props): JSX.Element {
  const { t } = useTranslation();
  const [name, setName] = useState(initial?.name ?? "");
  const [email, setEmail] = useState(initial?.contact_email ?? "");
  const [phone, setPhone] = useState(initial?.contact_phone ?? "");
  const [address, setAddress] = useState(initial?.address ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    void onSubmit({
      name: name.trim(),
      contact_email: email.trim() === "" ? null : email.trim(),
      contact_phone: phone.trim() === "" ? null : phone.trim(),
      address: address.trim() === "" ? null : address.trim(),
      notes: notes.trim() === "" ? null : notes.trim(),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <label className="block text-sm">
        <span className="block text-slate-700">
          {t("suppliers.fields.name")}
        </span>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          maxLength={160}
          className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
        />
      </label>
      <label className="block text-sm">
        <span className="block text-slate-700">
          {t("suppliers.fields.email")}
        </span>
        <input
          type="email"
          value={email ?? ""}
          onChange={(e) => setEmail(e.target.value)}
          maxLength={254}
          className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
        />
      </label>
      <label className="block text-sm">
        <span className="block text-slate-700">
          {t("suppliers.fields.phone")}
        </span>
        <input
          type="tel"
          value={phone ?? ""}
          onChange={(e) => setPhone(e.target.value)}
          maxLength={40}
          className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
        />
      </label>
      <label className="block text-sm">
        <span className="block text-slate-700">
          {t("suppliers.fields.address")}
        </span>
        <input
          type="text"
          value={address ?? ""}
          onChange={(e) => setAddress(e.target.value)}
          maxLength={255}
          className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
        />
      </label>
      <label className="block text-sm">
        <span className="block text-slate-700">
          {t("suppliers.fields.notes")}
        </span>
        <textarea
          value={notes ?? ""}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
        />
      </label>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700 disabled:opacity-60"
        >
          {submitting ? t("common.submitting") : t("costs.save")}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
          >
            {t("costs.cancel")}
          </button>
        )}
      </div>
    </form>
  );
}
