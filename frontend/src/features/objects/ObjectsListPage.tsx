import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { listObjects } from "./api";
import { apiErrorMessage } from "@/lib/apiError";
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
          setError(apiErrorMessage(e, t("common.error")));
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
            className="rounded bg-ink px-3 py-1 text-sm text-paper hover:bg-ink"
          >
            {t("objects.list.create")}
          </Link>
        }
      />

      {error && <p className="text-negative">{error}</p>}
      {objects === null && !error && <p className="text-ink-muted">{t("common.loading")}</p>}
      {objects && objects.length === 0 && (
        <p className="text-ink-muted">{t("objects.list.empty")}</p>
      )}
      {objects && objects.length > 0 && (
        <ul className="divide-y rounded border border-rule">
          {objects.map((o) => (
            <li key={o.id} className="p-3 hover:bg-paper-sunk">
              <Link to={`/objekte/${o.id}`} className="flex justify-between">
                <span className="font-medium">{o.name}</span>
                <span className="text-sm text-ink-muted">
                  {t(`objects.type.${o.type}`)}
                </span>
              </Link>
              {o.address && <p className="text-sm text-ink-muted">{o.address}</p>}
            </li>
          ))}
        </ul>
      )}
    </PageContainer>
  );
}
