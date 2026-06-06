import { useTranslation } from "react-i18next";

export function App(): JSX.Element {
  const { t } = useTranslation();
  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-semibold tracking-tight">{t("app.title")}</h1>
      <p className="mt-2 text-slate-600">{t("app.subtitle")}</p>
      <p className="mt-6 text-sm text-slate-500">
        {t("app.version")}: <code>0.1.0</code>
      </p>
    </main>
  );
}
