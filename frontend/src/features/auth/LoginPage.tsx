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
    <div className="mx-auto mt-16 max-w-md border border-rule bg-paper-raised p-8 shadow-panel">
      <h1 className="mb-6 font-display text-3xl text-ink">{t("auth.login.title")}</h1>
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
            className="block w-full rounded border border-rule px-3 py-2"
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
            className="block w-full rounded border border-rule px-3 py-2"
          />
        </label>

        {error && (
          <p role="alert" className="text-sm text-negative">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-ink px-4 py-2 text-paper disabled:opacity-50"
        >
          {submitting ? t("common.submitting") : t("auth.login.submit")}
        </button>
      </form>

      <p className="mt-4 text-sm">
        <Link to="/passwort-zuruecksetzen" className="text-ink-muted underline">
          {t("auth.login.forgot")}
        </Link>
      </p>
    </div>
  );
}
