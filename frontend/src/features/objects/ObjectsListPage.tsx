import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ApiError } from "@/api/client";
import { listObjects } from "./api";
import type { ObjectPublic } from "./types";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";

/**
 * Lists every object the current user has any membership on. Empty state
 * nudges the user toward creating their first object.
 */
export function ObjectsListPage(): JSX.Element {
  const { t } = useTranslation();
  const [objects, setObjects] = useState<ObjectPublic[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await listObjects();
        if (!cancelled) setObjects(data);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof ApiError ? String(e.detail) : t("common.error"));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [t]);

  return (
    <PageContainer width="narrow">
      <PageHeader
        title={t("objects.list.title")}
        actions={
          <Link
            to="/objekte/neu"
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
          >
            {t("objects.list.create")}
          </Link>
        }
      />

      {error && <p className="text-red-700">{error}</p>}
      {objects === null && !error && <p className="text-slate-500">{t("common.loading")}</p>}
      {objects && objects.length === 0 && (
        <p className="text-slate-600">{t("objects.list.empty")}</p>
      )}
      {objects && objects.length > 0 && (
        <ul className="divide-y rounded border border-slate-200">
          {objects.map((o) => (
            <li key={o.id} className="p-3 hover:bg-slate-50">
              <Link to={`/objekte/${o.id}`} className="flex justify-between">
                <span className="font-medium">{o.name}</span>
                <span className="text-sm text-slate-500">
                  {t(`objects.type.${o.type}`)}
                </span>
              </Link>
              {o.address && <p className="text-sm text-slate-500">{o.address}</p>}
            </li>
          ))}
        </ul>
      )}
    </PageContainer>
  );
}
