import { useState } from "react";
import { useTranslation } from "react-i18next";
import { apiRequest } from "@/api/client";

export function PasswordResetRequestPage(): JSX.Element {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await apiRequest<void>("/auth/password-reset/request", {
        method: "POST",
        json: { email },
      });
    } finally {
      setSent(true);
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <div className="mx-auto mt-16 max-w-md rounded-lg bg-white p-8 shadow">
        <h1 className="mb-2 text-2xl font-semibold">{t("auth.reset.requestTitle")}</h1>
        <p className="text-slate-700">{t("auth.reset.requestSent")}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto mt-16 max-w-md rounded-lg bg-white p-8 shadow">
      <h1 className="mb-6 text-2xl font-semibold">{t("auth.reset.requestTitle")}</h1>
      <form
        onSubmit={(e) => {
          void onSubmit(e);
        }}
        className="space-y-4"
      >
        <label className="block">
          <span className="mb-1 block text-sm font-medium">{t("auth.login.email")}</span>
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="block w-full rounded border border-slate-300 px-3 py-2"
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? t("common.submitting") : t("auth.reset.requestSubmit")}
        </button>
      </form>
    </div>
  );
}
