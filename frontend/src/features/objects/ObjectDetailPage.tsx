import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { getObject } from "./api";
import { apiErrorMessage } from "@/lib/apiError";
import type { ObjectDetail } from "./types";
import { UnitEditor } from "./UnitEditor";
import { AttachmentList } from "@/features/attachments/AttachmentList";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { ObjectProjectsSection } from "@/features/projects/ObjectProjectsSection";

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
          setError(apiErrorMessage(e, t("common.error")));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, t]);

  if (error)
    return (
      <PageContainer width="narrow">
        <p className="text-red-700">{error}</p>
      </PageContainer>
    );
  if (!obj)
    return (
      <PageContainer width="narrow">
        <p className="text-slate-500">{t("common.loading")}</p>
      </PageContainer>
    );

  return (
    <PageContainer width="narrow">
      <PageHeader
        title={obj.name}
        subtitle={
          <>
            {t(`objects.type.${obj.type}`)}
            {obj.address && ` — ${obj.address}`}
          </>
        }
      />

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

      <ObjectProjectsSection objectId={obj.id} />

      <section className="mb-8">
        <AttachmentList targetType="object" targetId={obj.id} canEdit />
      </section>
    </PageContainer>
  );
}
