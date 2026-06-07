/**
 * Tags + tag-assignment API client + TanStack Query hooks (Phase 11A).
 *
 * Tags are per-object; assignments attach a tag to a polymorphic target
 * (`project` | `cost_item`). The backend rejects cross-object
 * assignments with 422.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import {
  tagAssignmentSchema,
  tagSchema,
  type Tag,
  type TagAssignment,
  type TagCreate,
  type TagTargetType,
  type TagUpdate,
} from "./types";

export async function fetchTags(objectId: string): Promise<Tag[]> {
  const raw = await apiRequest<unknown[]>(`/objects/${objectId}/tags`);
  return raw.map((t) => tagSchema.parse(t));
}

export async function createTag(
  objectId: string,
  payload: TagCreate,
): Promise<Tag> {
  const raw = await apiRequest<unknown>(`/objects/${objectId}/tags`, {
    method: "POST",
    json: payload,
    withCsrf: true,
  });
  return tagSchema.parse(raw);
}

export async function updateTag(tagId: string, payload: TagUpdate): Promise<Tag> {
  const raw = await apiRequest<unknown>(`/tags/${tagId}`, {
    method: "PATCH",
    json: payload,
    withCsrf: true,
  });
  return tagSchema.parse(raw);
}

export async function deleteTag(tagId: string): Promise<void> {
  await apiRequest<void>(`/tags/${tagId}`, {
    method: "DELETE",
    withCsrf: true,
  });
}

export async function assignTag(
  tagId: string,
  target: { target_type: TagTargetType; target_id: string },
): Promise<TagAssignment> {
  const raw = await apiRequest<unknown>(`/tags/${tagId}/assignments`, {
    method: "POST",
    json: target,
    withCsrf: true,
  });
  return tagAssignmentSchema.parse(raw);
}

export async function unassignTag(
  tagId: string,
  target: { target_type: TagTargetType; target_id: string },
): Promise<void> {
  await apiRequest<void>(
    `/tags/${tagId}/assignments/${target.target_type}/${target.target_id}`,
    { method: "DELETE", withCsrf: true },
  );
}

export async function fetchTagsForTarget(
  targetType: TagTargetType,
  targetId: string,
): Promise<Tag[]> {
  const raw = await apiRequest<unknown[]>(`/${targetType}/${targetId}/tags`);
  return raw.map((t) => tagSchema.parse(t));
}

// --- hooks -----------------------------------------------------------------

export const tagsKey = (objectId: string) => ["tags", objectId] as const;
export const targetTagsKey = (targetType: TagTargetType, targetId: string) =>
  ["target-tags", targetType, targetId] as const;

export function useTags(objectId: string): UseQueryResult<Tag[]> {
  return useQuery({
    queryKey: tagsKey(objectId),
    queryFn: () => fetchTags(objectId),
    enabled: Boolean(objectId),
  });
}

export function useTagsForTarget(
  targetType: TagTargetType,
  targetId: string,
): UseQueryResult<Tag[]> {
  return useQuery({
    queryKey: targetTagsKey(targetType, targetId),
    queryFn: () => fetchTagsForTarget(targetType, targetId),
    enabled: Boolean(targetId),
  });
}

export function useCreateTag(
  objectId: string,
): UseMutationResult<Tag, Error, TagCreate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: TagCreate) => createTag(objectId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: tagsKey(objectId) });
    },
  });
}

export function useUpdateTag(
  objectId: string,
): UseMutationResult<Tag, Error, { tagId: string; payload: TagUpdate }> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tagId, payload }) => updateTag(tagId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: tagsKey(objectId) });
      void qc.invalidateQueries({ queryKey: ["target-tags"] });
    },
  });
}

export function useDeleteTag(
  objectId: string,
): UseMutationResult<void, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (tagId: string) => deleteTag(tagId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: tagsKey(objectId) });
      void qc.invalidateQueries({ queryKey: ["target-tags"] });
    },
  });
}

interface AssignVars {
  tagId: string;
  targetType: TagTargetType;
  targetId: string;
}

export function useAssignTag(): UseMutationResult<TagAssignment, Error, AssignVars> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tagId, targetType, targetId }) =>
      assignTag(tagId, { target_type: targetType, target_id: targetId }),
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({
        queryKey: targetTagsKey(vars.targetType, vars.targetId),
      });
    },
  });
}

export function useUnassignTag(): UseMutationResult<void, Error, AssignVars> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tagId, targetType, targetId }) =>
      unassignTag(tagId, { target_type: targetType, target_id: targetId }),
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({
        queryKey: targetTagsKey(vars.targetType, vars.targetId),
      });
    },
  });
}
