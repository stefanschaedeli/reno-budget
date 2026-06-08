import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";

export function HomePage(): JSX.Element {
  const { t } = useTranslation();
  const { user } = useAuth();

  return (
    <PageContainer width="narrow">
      <PageHeader title={t("app.title")} subtitle={t("app.subtitle")} />
      {user && (
        <p className="mb-4 text-sm text-slate-500">
          {t("auth.me.greeting", { name: user.display_name })}
        </p>
      )}
      <nav className="flex gap-2">
        <Link
          to="/objekte"
          className="inline-block rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-700"
        >
          {t("objects.list.title")}
        </Link>
        <Link
          to="/finanzen"
          className="inline-block rounded border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100"
        >
          {t("budget.nav")}
        </Link>
      </nav>
    </PageContainer>
  );
}
