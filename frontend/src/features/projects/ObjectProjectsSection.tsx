import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Drawer } from "@/components/Drawer";
import { formatChf } from "@/features/costs/types";
import { ProjectForm } from "./ProjectForm";
import { useCreateProject, useProjects } from "./api";
import { PROJECT_STATUSES, type Project, type ProjectCreate, type ProjectStatus } from "./types";

type StatusFilter = "all" | ProjectStatus;

/**
 * Inline Projects section embedded on the Object detail page.
 *
 * Replaces the standalone per-object /objekte/:id/projekte sub-page so
 * Projects appear as the primary action inside an Object.
 */
export function ObjectProjectsSection({
  objectId,
}: {
  objectId: string;
}): JSX.Element {
  const { t } = useTranslation();
  const [creating, setCreating] = useState(false);
  const [filter, setFilter] = useState<StatusFilter>("all");

  const projectsQuery = useProjects(objectId);
  const createMut = useCreateProject(objectId);

  const projects = projectsQuery.data ?? [];
  const filtered = useMemo(
    () => (filter === "all" ? projects : projects.filter((p) => p.status === filter)),
    [projects, filter],
  );

  const handleCreate = async (payload: ProjectCreate) => {
    await createMut.mutateAsync(payload);
    setCreating(false);
  };

  return (
    <section className="mb-8">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-lg font-medium">{t("projects.title")}</h3>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="rounded bg-ink px-3 py-1 text-sm text-paper hover:bg-ink"
        >
          {t("projects.create")}
        </button>
      </div>

      {projects.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1">
          <StatusChip
            label={t("projects.filter.all")}
            active={filter === "all"}
            onClick={() => setFilter("all")}
          />
          {PROJECT_STATUSES.map((s) => (
            <StatusChip
              key={s}
              label={t(`projects.status.${s}`)}
              active={filter === s}
              onClick={() => setFilter(s)}
            />
          ))}
        </div>
      )}

      {projectsQuery.isLoading && (
        <p className="text-ink-muted">{t("common.loading")}</p>
      )}
      {projectsQuery.isError && (
        <p className="text-negative">{t("common.error")}</p>
      )}
      {projectsQuery.isSuccess && projects.length === 0 && (
        <div className="rounded border border-dashed border-rule px-4 py-8 text-center text-sm text-ink-muted">
          {t("projects.emptyInObject")}
        </div>
      )}
      {filtered.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-ink-muted">
            <tr className="border-b border-rule">
              <th className="px-2 py-2">{t("projects.fields.name")}</th>
              <th className="px-2 py-2">{t("projects.fields.status")}</th>
              <th className="px-2 py-2 text-right">
                {t("projects.fields.roughEstimate")}
              </th>
              <th className="px-2 py-2">{t("projects.fields.plannedYear")}</th>
              <th className="px-2 py-2">{t("projects.fields.updatedAt")}</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p: Project) => (
              <tr
                key={p.id}
                data-testid={`project-row-${p.id}`}
                className="border-b border-rule hover:bg-paper-sunk"
              >
                <td className="px-2 py-2 font-medium">
                  <Link to={`/projekte/${p.id}`} className="hover:underline">
                    {p.name}
                  </Link>
                </td>
                <td className="px-2 py-2">{t(`projects.status.${p.status}`)}</td>
                <td className="px-2 py-2 text-right tabular-nums">
                  {p.rough_estimate_chf != null
                    ? formatChf(String(p.rough_estimate_chf))
                    : "—"}
                </td>
                <td className="px-2 py-2">{p.planned_year ?? "—"}</td>
                <td className="px-2 py-2 text-ink-muted">
                  {new Date(p.updated_at).toLocaleDateString("de-CH")}
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

function StatusChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-3 py-0.5 text-xs ${
        active
          ? "border-ink bg-ink text-paper"
          : "border-rule text-ink-muted hover:bg-paper-sunk"
      }`}
    >
      {label}
    </button>
  );
}
