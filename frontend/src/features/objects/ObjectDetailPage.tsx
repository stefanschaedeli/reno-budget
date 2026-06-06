import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { getObject } from "./api";
import type { ObjectDetail } from "./types";
import { UnitEditor } from "./UnitEditor";
import { AttachmentList } from "@/features/attachments/AttachmentList";

/**
 * Read-only object detail page. Phase 2 stops here for unit editing — the
 * full per-unit editor with save semantics arrives in Phase 3 alongside
 * cost items, which need stable unit IDs to allocate against.
 */
export function ObjectDetailPage(): JSX.Element {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const [obj, setObj] = useState<ObjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await getObject(id);
        if (!cancelled) setObj(data);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof ApiError ? String(e.detail) : t("common.error"));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, t]);

  if (error) return <p className="mx-auto mt-12 max-w-3xl p-6 text-red-700">{error}</p>;
  if (!obj) return <p className="mx-auto mt-12 max-w-3xl p-6 text-slate-500">{t("common.loading")}</p>;

  return (
    <section className="mx-auto mt-12 max-w-3xl p-6">
      <header className="mb-6">
        <h2 className="text-2xl font-semibold">{obj.name}</h2>
        <p className="text-slate-500">
          {t(`objects.type.${obj.type}`)}
          {obj.address && ` — ${obj.address}`}
        </p>
        <nav className="mt-3 flex gap-3 text-sm">
          <Link
            to={`/objekte/${obj.id}/kosten`}
            className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100"
          >
            {t("costs.title")}
          </Link>
          <Link
            to={`/objekte/${obj.id}/budget`}
            className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100"
          >
            {t("budget.tab")}
          </Link>
        </nav>
      </header>

      <section className="mb-8">
        <h3 className="mb-2 text-lg font-medium">{t("objects.units.title")}</h3>
        <UnitEditor
          units={obj.units.map((u) => ({
            label: u.label,
            wertquote_permille: u.wertquote_permille,
            area_m2: u.area_m2,
          }))}
          onChange={() => {
            /* read-only in Phase 2; see Phase 3 plan entry */
          }}
          readonly
        />
      </section>

      <section className="mb-8">
        <AttachmentList targetType="object" targetId={obj.id} canEdit />
      </section>
    </section>
  );
}
