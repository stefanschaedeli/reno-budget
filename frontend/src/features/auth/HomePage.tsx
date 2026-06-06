import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function HomePage(): JSX.Element {
  const { t } = useTranslation();
  const { user, logout } = useAuth();

  return (
    <div className="mx-auto mt-12 max-w-3xl p-6">
      <header className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-semibold">{t("app.title")}</h1>
        <button
          type="button"
          onClick={() => void logout()}
          className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
        >
          {t("auth.logout")}
        </button>
      </header>
      <p className="text-slate-600">{t("app.subtitle")}</p>
      {user && (
        <p className="mt-4 text-sm text-slate-500">
          {t("auth.me.greeting", { name: user.display_name })}
        </p>
      )}
      <nav className="mt-6">
        <Link
          to="/objekte"
          className="inline-block rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-700"
        >
          {t("objects.list.title")}
        </Link>
      </nav>
    </div>
  );
}
