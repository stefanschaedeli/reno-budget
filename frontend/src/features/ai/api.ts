/**
 * API client + React Query hooks for the AI Project Assistant.
 *
 * Endpoints are project-scoped under
 * `/objects/{objectId}/projects/{projectId}/ai/...`. Mutations use the
 * double-submit CSRF cookie (`withCsrf: true`).
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import { apiRequest } from "@/api/client";

import { artifactSchema, sessionSchema, type AiArtifact, type AiSession, type AiStep } from "./types";

function base(objectId: string, projectId: string): string {
  return `/objects/${objectId}/projects/${projectId}/ai`;
}

export const aiSessionKey = (objectId: string, projectId: string) =>
  ["ai", "session", objectId, projectId] as const;

export async function fetchSession(
  objectId: string,
  projectId: string,
): Promise<AiSession> {
  const raw = await apiRequest<unknown>(`${base(objectId, projectId)}/session`);
  return sessionSchema.parse(raw);
}

export function useAiSession(
  objectId: string,
  projectId: string,
  enabled: boolean,
): UseQueryResult<AiSession> {
  return useQuery({
    queryKey: aiSessionKey(objectId, projectId),
    queryFn: () => fetchSession(objectId, projectId),
    enabled: enabled && Boolean(objectId) && Boolean(projectId),
  });
}

export async function runStep(
  objectId: string,
  projectId: string,
  step: AiStep,
): Promise<AiArtifact> {
  const raw = await apiRequest<unknown>(`${base(objectId, projectId)}/run`, {
    method: "POST",
    json: { step },
    withCsrf: true,
  });
  return artifactSchema.parse(raw);
}

export function useRunStep(
  objectId: string,
  projectId: string,
): UseMutationResult<AiArtifact, Error, AiStep> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (step: AiStep) => runStep(objectId, projectId, step),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: aiSessionKey(objectId, projectId) });
    },
  });
}

export async function submitAnswers(
  objectId: string,
  projectId: string,
  answers: Record<string, unknown>,
): Promise<AiSession> {
  const raw = await apiRequest<unknown>(`${base(objectId, projectId)}/answers`, {
    method: "POST",
    json: { answers },
    withCsrf: true,
  });
  return sessionSchema.parse(raw);
}

export function useSubmitAnswers(
  objectId: string,
  projectId: string,
): UseMutationResult<AiSession, Error, Record<string, unknown>> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (answers: Record<string, unknown>) =>
      submitAnswers(objectId, projectId, answers),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: aiSessionKey(objectId, projectId) });
    },
  });
}

export async function acceptArtifact(
  objectId: string,
  projectId: string,
  artifactId: string,
): Promise<AiArtifact> {
  const raw = await apiRequest<unknown>(
    `${base(objectId, projectId)}/artifacts/${artifactId}/accept`,
    { method: "POST", withCsrf: true },
  );
  return artifactSchema.parse(raw);
}

export function useAcceptArtifact(
  objectId: string,
  projectId: string,
): UseMutationResult<AiArtifact, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (artifactId: string) =>
      acceptArtifact(objectId, projectId, artifactId),
    onSuccess: () => {
      // The accept wrote real Project / CostItem data — refresh those too.
      void qc.invalidateQueries({ queryKey: aiSessionKey(objectId, projectId) });
      void qc.invalidateQueries({ queryKey: ["projects"] });
      void qc.invalidateQueries({ queryKey: ["cost-items"] });
    },
  });
}
