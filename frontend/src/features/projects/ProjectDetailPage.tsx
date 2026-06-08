/**
 * Project detail / edit page.
 *
 * Shows project metadata, an edit form, archive + delete buttons and
 * the list of cost items belonging to the project. Cost items are
 * fetched from the existing cost-items endpoint filtered by project_id.
 */
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { useCostItems } from "@/api/costs";
import { formatChf } from "@/features/costs/types";
import { ProjectForm } from "./ProjectForm";
import {
  useArchiveProject,
  useDeleteProject,
  useProject,
  useUpdateProject,
} from "./api";
import type { ProjectCreate } from "./types";
import { useTagsForTarget } from "@/features/tags/api";
import { TagChip } from "@/components/TagChip";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";

export function ProjectDetailPage(): JSX.Element {
  const { t } = useTranslation();
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const projectQuery = useProject(projectId ?? "");
  const updateMut = useUpdateProject(projectId ?? "");
  const archiveMut = useArchiveProject(projectId ?? "");
  const objectId = projectQuery.data?.object_id ?? "";
  const deleteMut = useDeleteProject(projectId ?? "", objectId);
  const costItemsQuery = useCostItems(objectId, { project_id: projectId });
  const tagsQuery = useTagsForTarget("project", projectId ?? "");

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

  const project = projectQuery.data;
  const items = costItemsQuery.data ?? [];
  const tags = tagsQuery.data ?? [];

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
    navigate(`/objekte/${project.object_id}/projekte`);
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

      <section className="mb-8">
        <h3 className="mb-3 text-lg font-medium">{t("projects.edit")}</h3>
        <ProjectForm
          initial={{
            name: project.name,
            description: project.description,
            status: project.status,
            planned_year: project.planned_year,
          }}
          onSubmit={handleSubmit}
          submitting={updateMut.isPending}
        />
      </section>

      <section className="mb-8">
        <h3 className="mb-3 text-lg font-medium">
          {t("projects.costItems.title")}
        </h3>
        {costItemsQuery.isLoading && (
          <p className="text-slate-500">{t("common.loading")}</p>
        )}
        {items.length === 0 && !costItemsQuery.isLoading && (
          <p className="text-slate-500">{t("projects.costItems.empty")}</p>
        )}
        {items.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-600">
              <tr className="border-b border-slate-300">
                <th className="px-2 py-2">{t("costs.fields.title")}</th>
                <th className="px-2 py-2">{t("costs.fields.bkp")}</th>
                <th className="px-2 py-2 text-right">
                  {t("costs.fields.plannedAmount")}
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b border-slate-200">
                  <td className="px-2 py-2 font-medium">{item.title}</td>
                  <td className="px-2 py-2 font-mono text-xs">
                    {item.bkp_code ?? t("costs.uncategorised")}
                  </td>
                  <td className="px-2 py-2 text-right tabular-nums">
                    {formatChf(item.planned_amount_chf)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
