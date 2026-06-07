/**
 * Per-object project list view.
 *
 * Shows one row per project with status, planned year, archived state
 * and a quick cost-item-count derived from the existing cost-items
 * query. Provides inline create via a drawer.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { useCostItems } from "@/api/costs";
import { ProjectForm } from "./ProjectForm";
import { useCreateProject, useProjects } from "./api";
import type { Project, ProjectCreate } from "./types";

export function ProjectsPage(): JSX.Element {
  const { t } = useTranslation();
  const { objectId } = useParams<{ objectId: string }>();
  const [includeArchived, setIncludeArchived] = useState(false);
  const [creating, setCreating] = useState(false);

  const projectsQuery = useProjects(objectId ?? "", { includeArchived });
  const costItemsQuery = useCostItems(objectId ?? "", {});
  const createMut = useCreateProject(objectId ?? "");

  if (!objectId) {
    return (
      <p className="mx-auto mt-12 max-w-5xl p-6 text-red-700">
        {t("common.error")}
      </p>
    );
  }

  const projects = projectsQuery.data ?? [];
  const costItems = costItemsQuery.data ?? [];
  const countByProject = new Map<string, number>();
  for (const c of costItems) {
    if (c.project_id) {
      countByProject.set(c.project_id, (countByProject.get(c.project_id) ?? 0) + 1);
    }
  }

  const handleCreate = async (payload: ProjectCreate) => {
    await createMut.mutateAsync(payload);
    setCreating(false);
  };

  return (
    <section className="mx-auto mt-8 max-w-5xl p-6">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">{t("projects.title")}</h2>
          <p className="text-slate-500">{t("projects.subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
        >
          {t("projects.create")}
        </button>
      </header>

      <label className="mb-3 inline-flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
        />
        {t("projects.includeArchived")}
      </label>

      {projectsQuery.isLoading && (
        <p className="text-slate-500">{t("common.loading")}</p>
      )}
      {projectsQuery.isError && (
        <p className="text-red-700">{t("common.error")}</p>
      )}
      {projectsQuery.isSuccess && projects.length === 0 && (
        <p className="text-slate-500">{t("projects.empty")}</p>
      )}
      {projects.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
              <th className="px-2 py-2">{t("projects.fields.name")}</th>
              <th className="px-2 py-2">{t("projects.fields.status")}</th>
              <th className="px-2 py-2">{t("projects.fields.plannedYear")}</th>
              <th className="px-2 py-2 text-right">{t("projects.fields.itemCount")}</th>
              <th className="px-2 py-2">{t("projects.fields.archivedAt")}</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p: Project) => (
              <tr
                key={p.id}
                data-testid={`project-row-${p.id}`}
                className="border-b border-slate-200 hover:bg-slate-50"
              >
                <td className="px-2 py-2 font-medium">
                  <Link to={`/projects/${p.id}`} className="hover:underline">
                    {p.name}
                  </Link>
                </td>
                <td className="px-2 py-2">
                  {t(`projects.status.${p.status}`)}
                </td>
                <td className="px-2 py-2">{p.planned_year ?? "—"}</td>
                <td className="px-2 py-2 text-right tabular-nums">
                  {countByProject.get(p.id) ?? 0}
                </td>
                <td className="px-2 py-2 text-slate-500">
                  {p.archived_at
                    ? new Date(p.archived_at).toLocaleDateString("de-CH")
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {creating && (
        <Drawer title={t("projects.create")} onClose={() => setCreating(false)}>
          <ProjectForm
            onSubmit={handleCreate}
            onCancel={() => setCreating(false)}
            submitting={createMut.isPending}
          />
        </Drawer>
      )}
    </section>
  );
}

interface DrawerProps {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

function Drawer({ title, onClose, children }: DrawerProps): JSX.Element {
  return (
    <div className="fixed inset-0 z-40 flex">
      <div
        className="flex-1 bg-slate-900/40"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside className="z-50 w-full max-w-xl overflow-y-auto bg-white p-6 shadow-xl">
        <header className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label="Schliessen"
            className="text-slate-500 hover:text-slate-900"
          >
            ×
          </button>
        </header>
        {children}
      </aside>
    </div>
  );
}
