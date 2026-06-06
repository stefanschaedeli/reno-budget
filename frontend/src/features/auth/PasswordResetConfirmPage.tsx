import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, apiRequest } from "@/api/client";

export function PasswordResetConfirmPage(): JSX.Element {
  const { t } = useTranslation();
  const { token = "" } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await apiRequest<void>("/auth/password-reset/confirm", {
        method: "POST",
        json: { token, new_password: password },
      });
      setSuccess(true);
      setTimeout(() => navigate("/anmelden"), 1500);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 422) setError(String(err.detail));
        else setError(t("auth.reset.errorInvalid"));
      } else {
        setError(t("auth.reset.errorInvalid"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="mx-auto mt-16 max-w-md rounded-lg bg-white p-8 shadow">
        <h1 className="mb-2 text-2xl font-semibold">{t("auth.reset.confirmTitle")}</h1>
        <p className="text-emerald-700">{t("auth.reset.confirmSuccess")}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto mt-16 max-w-md rounded-lg bg-white p-8 shadow">
      <h1 className="mb-6 text-2xl font-semibold">{t("auth.reset.confirmTitle")}</h1>
      <form
        onSubmit={(e) => {
          void onSubmit(e);
        }}
        className="space-y-4"
      >
        <label className="block">
          <span className="mb-1 block text-sm font-medium">{t("auth.reset.newPassword")}</span>
          <input
            type="password"
            autoComplete="new-password"
            minLength={12}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="block w-full rounded border border-slate-300 px-3 py-2"
          />
          <span className="mt-1 block text-xs text-slate-500">{t("auth.invite.passwordHint")}</span>
        </label>

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? t("common.submitting") : t("auth.reset.confirmSubmit")}
        </button>
      </form>
    </div>
  );
}
