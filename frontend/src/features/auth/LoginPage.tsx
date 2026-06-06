import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import { useAuth } from "./AuthContext";

export function LoginPage(): JSX.Element {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password });
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 423) setError(t("auth.login.errorLocked"));
        else if (err.status === 403) setError(t("auth.login.errorInactive"));
        else if (err.status === 429) setError(t("auth.login.errorRateLimited"));
        else setError(t("auth.login.errorGeneric"));
      } else {
        setError(t("auth.login.errorGeneric"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-md rounded-lg bg-white p-8 shadow">
      <h1 className="mb-6 text-2xl font-semibold">{t("auth.login.title")}</h1>
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
        <label className="block">
          <span className="mb-1 block text-sm font-medium">{t("auth.login.password")}</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="block w-full rounded border border-slate-300 px-3 py-2"
          />
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
          {submitting ? t("common.submitting") : t("auth.login.submit")}
        </button>
      </form>

      <p className="mt-4 text-sm">
        <Link to="/passwort-zuruecksetzen" className="text-slate-600 underline">
          {t("auth.login.forgot")}
        </Link>
      </p>
    </div>
  );
}
