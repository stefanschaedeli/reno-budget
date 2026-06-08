/**
 * Projects API client + TanStack Query hooks (Phase 11A).
 *
 * All mutating endpoints attach CSRF via the shared client wrapper
 * (`withCsrf: true`). Projects belong to a single object; the list query
 * is keyed by object id + archived-filter flag.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { z } from "zod";
import { apiRequest } from "@/api/client";
import {
  projectListItemSchema,
  projectSchema,
  type Project,
  type ProjectCreate,
  type ProjectListItem,
  type ProjectUpdate,
} from "./types";

export async function fetchProjects(
  objectId: string,
  opts: { includeArchived?: boolean } = {},
): Promise<Project[]> {
  const qs = opts.includeArchived ? "?include_archived=true" : "";
  const raw = await apiRequest<unknown[]>(
    `/objects/${objectId}/projects${qs}`,
  );
  return raw.map((p) => projectSchema.parse(p));
}

export async function fetchAllProjects(): Promise<ProjectListItem[]> {
  const raw = await apiRequest<unknown>(`/projects`);
  return z.array(projectListItemSchema).parse(raw);
}

export function useAllProjects(): UseQueryResult<ProjectListItem[]> {
  return useQuery({
    queryKey: ["projects-all"],
    queryFn: fetchAllProjects,
  });
}

export async function fetchProject(projectId: string): Promise<Project> {
  const raw = await apiRequest<unknown>(`/projects/${projectId}`);
  return projectSchema.parse(raw);
}

export async function createProject(
  objectId: string,
  payload: ProjectCreate,
): Promise<Project> {
  const raw = await apiRequest<unknown>(`/objects/${objectId}/projects`, {
    method: "POST",
    json: payload,
    withCsrf: true,
  });
  return projectSchema.parse(raw);
}

export async function updateProject(
  projectId: string,
  payload: ProjectUpdate,
): Promise<Project> {
  const raw = await apiRequest<unknown>(`/projects/${projectId}`, {
    method: "PATCH",
    json: payload,
    withCsrf: true,
  });
  return projectSchema.parse(raw);
}

export async function archiveProject(projectId: string): Promise<Project> {
  const raw = await apiRequest<unknown>(`/projects/${projectId}/archive`, {
    method: "POST",
    withCsrf: true,
  });
  return projectSchema.parse(raw);
}

export async function deleteProject(projectId: string): Promise<void> {
  await apiRequest<void>(`/projects/${projectId}`, {
    method: "DELETE",
    withCsrf: true,
  });
}

// --- hooks -----------------------------------------------------------------

export const projectsKey = (objectId: string, includeArchived: boolean) =>
  ["projects", objectId, includeArchived] as const;

export function useProjects(
  objectId: string,
  opts: { includeArchived?: boolean } = {},
): UseQueryResult<Project[]> {
  const includeArchived = opts.includeArchived ?? false;
  return useQuery({
    queryKey: projectsKey(objectId, includeArchived),
    queryFn: () => fetchProjects(objectId, { includeArchived }),
    enabled: Boolean(objectId),
  });
}

export function useProject(projectId: string): UseQueryResult<Project> {
  return useQuery({
    queryKey: ["project", projectId] as const,
    queryFn: () => fetchProject(projectId),
    enabled: Boolean(projectId),
  });
}

export function useCreateProject(
  objectId: string,
): UseMutationResult<Project, Error, ProjectCreate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProjectCreate) => createProject(objectId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects", objectId] });
    },
  });
}

export function useUpdateProject(
  projectId: string,
): UseMutationResult<Project, Error, ProjectUpdate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProjectUpdate) => updateProject(projectId, payload),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["projects", data.object_id] });
      void qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}

export function useArchiveProject(
  projectId: string,
): UseMutationResult<Project, Error, void> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => archiveProject(projectId),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["projects", data.object_id] });
      void qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });
}

export function useDeleteProject(
  projectId: string,
  objectId: string,
): UseMutationResult<void, Error, void> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => deleteProject(projectId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["projects", objectId] });
    },
  });
}
