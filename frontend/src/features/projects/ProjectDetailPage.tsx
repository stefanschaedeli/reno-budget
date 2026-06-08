/**
 * Project detail page composed from a budget card, a cost-items
 * section, and a collapsible details panel (existing ProjectForm).
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { useCostItems } from "@/api/costs";
import { getObject } from "@/features/objects/api";
import type { ObjectDetail } from "@/features/objects/types";
import { apiErrorMessage } from "@/lib/apiError";
import { useTagsForTarget } from "@/features/tags/api";
import { TagChip } from "@/components/TagChip";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { ProjectForm } from "./ProjectForm";
import { BudgetCard } from "./BudgetCard";
import { ProjectCostItemsSection } from "./ProjectCostItemsSection";
import {
  useArchiveProject,
  useDeleteProject,
  useProject,
  useUpdateProject,
} from "./api";
import type { ProjectCreate } from "./types";

function sumPlanned(items: Array<{ planned_amount_chf: string | null }>): number {
  let total = 0;
  for (const i of items) {
    if (i.planned_amount_chf == null) continue;
    const n = Number(i.planned_amount_chf);
    if (Number.isFinite(n)) total += n;
  }
  return total;
}

export function ProjectDetailPage(): JSX.Element {
  const { t } = useTranslation();
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [object, setObject] = useState<ObjectDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const projectQuery = useProject(projectId ?? "");
  const updateMut = useUpdateProject(projectId ?? "");
  const archiveMut = useArchiveProject(projectId ?? "");
  const objectId = projectQuery.data?.object_id ?? "";
  const deleteMut = useDeleteProject(projectId ?? "", objectId);
  const costItemsQuery = useCostItems(objectId, { project_id: projectId });
  const tagsQuery = useTagsForTarget("project", projectId ?? "");

  useEffect(() => {
    if (!objectId) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await getObject(objectId);
        if (!cancelled) setObject(data);
      } catch (e) {
        if (!cancelled) setLoadError(apiErrorMessage(e, t("common.error")));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [objectId, t]);

  if (projectQuery.isLoading || !projectId) {
    return (
      <PageContainer width="narrow">
        <p className="text-slate-500">{t("common.loading")}</p>
      </PageContainer>
    );
  }
  if (projectQuery.isError || !projectQuery.data) {
    return (
      <PageContainer width="narrow">
        <p className="text-red-700">{t("common.error")}</p>
      </PageContainer>
    );
  }
  if (loadError) {
    return (
      <PageContainer width="narrow">
        <p className="text-red-700">{loadError}</p>
      </PageContainer>
    );
  }

  const project = projectQuery.data;
  const items = costItemsQuery.data ?? [];
  const tags = tagsQuery.data ?? [];
  const plannedTotal = sumPlanned(items);

  const handleSubmit = async (payload: ProjectCreate) => {
    await updateMut.mutateAsync(payload);
  };

  const handleArchive = async () => {
    if (!window.confirm(t("projects.archiveConfirm"))) return;
    await archiveMut.mutateAsync();
  };

  const handleDelete = async () => {
    if (!window.confirm(t("projects.deleteConfirm"))) return;
    await deleteMut.mutateAsync();
    navigate(`/objekte/${project.object_id}`);
  };

  return (
    <PageContainer width="narrow">
      <PageHeader
        title={project.name}
        subtitle={
          <>
            {t(`projects.status.${project.status}`)}
            {project.planned_year && ` · ${project.planned_year}`}
            {project.archived_at && ` · ${t("projects.archived")}`}
          </>
        }
      />

      {tags.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-1">
          {tags.map((tag) => (
            <TagChip key={tag.id} tag={tag} />
          ))}
        </div>
      )}

      <BudgetCard project={project} plannedTotal={plannedTotal} />

      {object && (
        <ProjectCostItemsSection
          objectId={objectId}
          projectId={projectId}
          object={object}
        />
      )}

      <section className="mb-8 border-t border-slate-200 pt-4">
        <button
          type="button"
          onClick={() => setDetailsOpen((v) => !v)}
          className="mb-3 text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          {detailsOpen
            ? t("projects.details.hide")
            : t("projects.details.show")}
        </button>
        {detailsOpen && (
          <ProjectForm
            initial={{
              name: project.name,
              description: project.description,
              status: project.status,
              planned_year: project.planned_year,
              rough_estimate_chf: project.rough_estimate_chf,
            }}
            onSubmit={handleSubmit}
            submitting={updateMut.isPending}
          />
        )}
      </section>

      <section className="border-t border-slate-200 pt-4">
        <div className="flex gap-2">
          {!project.archived_at && (
            <button
              type="button"
              onClick={() => void handleArchive()}
              className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
            >
              {t("projects.archive")}
            </button>
          )}
          <button
            type="button"
            onClick={() => void handleDelete()}
            className="rounded border border-red-300 px-3 py-1 text-sm text-red-700 hover:bg-red-50"
          >
            {t("projects.delete")}
          </button>
        </div>
      </section>
    </PageContainer>
  );
}
