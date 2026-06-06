/**
 * Renofond API client + TanStack Query hooks (Phase 5).
 *
 * Read endpoints work for any VIEWER+; mutations are OWNER-only. The
 * backend returns ``my_role`` on the contributions list so the UI can
 * gate the add/delete affordances without a separate round-trip.
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
  contributionListSchema,
  projectionResponseSchema,
  type ContributionCreate,
  type ContributionList,
  type ProjectionResponse,
} from "./types";

export async function fetchProjection(
  objectId: string,
): Promise<ProjectionResponse> {
  const raw = await apiRequest<unknown>(
    `/objects/${objectId}/renofond/projection`,
  );
  return projectionResponseSchema.parse(raw);
}

export async function fetchContributions(
  objectId: string,
): Promise<ContributionList> {
  const raw = await apiRequest<unknown>(
    `/objects/${objectId}/renofond/contributions`,
  );
  return contributionListSchema.parse(raw);
}

export async function createContribution(
  objectId: string,
  payload: ContributionCreate,
): Promise<unknown> {
  return apiRequest<unknown>(`/objects/${objectId}/renofond/contributions`, {
    method: "POST",
    json: payload,
    withCsrf: true,
  });
}

export async function deleteContribution(
  objectId: string,
  contributionId: string,
): Promise<void> {
  await apiRequest<unknown>(
    `/objects/${objectId}/renofond/contributions/${contributionId}`,
    { method: "DELETE", withCsrf: true },
  );
}

export const projectionKey = (objectId: string) =>
  ["renofond", "projection", objectId] as const;
export const contributionsKey = (objectId: string) =>
  ["renofond", "contributions", objectId] as const;

export function useProjection(
  objectId: string,
): UseQueryResult<ProjectionResponse> {
  return useQuery({
    queryKey: projectionKey(objectId),
    queryFn: () => fetchProjection(objectId),
    enabled: Boolean(objectId),
  });
}

export function useContributions(
  objectId: string,
): UseQueryResult<ContributionList> {
  return useQuery({
    queryKey: contributionsKey(objectId),
    queryFn: () => fetchContributions(objectId),
    enabled: Boolean(objectId),
  });
}

export function useCreateContribution(
  objectId: string,
): UseMutationResult<unknown, Error, ContributionCreate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ContributionCreate) =>
      createContribution(objectId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["renofond"] });
    },
  });
}

export function useDeleteContribution(
  objectId: string,
): UseMutationResult<void, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteContribution(objectId, id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["renofond"] });
    },
  });
}
