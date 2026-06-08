/**
 * Lots API client + TanStack Query hooks (Phase 11B).
 *
 * All mutating endpoints attach CSRF via the shared client wrapper
 * (`withCsrf: true`). Lots belong to a single object; membership is
 * managed via separate add/remove endpoints since lots are cross-project.
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
import { costItemSchema, type CostItem } from "@/features/costs/types";
import {
  lotListItemSchema,
  lotSchema,
  type Lot,
  type LotCostItemRef,
  type LotCreate,
  type LotListItem,
  type LotUpdate,
} from "./types";

export async function fetchLots(
  objectId: string,
  opts: { includeArchived?: boolean } = {},
): Promise<Lot[]> {
  const qs = opts.includeArchived ? "?include_archived=true" : "";
  const raw = await apiRequest<unknown[]>(`/objects/${objectId}/lots${qs}`);
  return raw.map((l) => lotSchema.parse(l));
}

export async function fetchAllLots(): Promise<LotListItem[]> {
  const raw = await apiRequest<unknown>(`/lots`);
  return z.array(lotListItemSchema).parse(raw);
}

export function useAllLots(): UseQueryResult<LotListItem[]> {
  return useQuery({
    queryKey: ["lots-all"],
    queryFn: fetchAllLots,
  });
}

export async function fetchLot(lotId: string): Promise<Lot> {
  const raw = await apiRequest<unknown>(`/lots/${lotId}`);
  return lotSchema.parse(raw);
}

export async function createLot(
  objectId: string,
  payload: LotCreate,
): Promise<Lot> {
  const raw = await apiRequest<unknown>(`/objects/${objectId}/lots`, {
    method: "POST",
    json: payload,
    withCsrf: true,
  });
  return lotSchema.parse(raw);
}

export async function updateLot(
  lotId: string,
  payload: LotUpdate,
): Promise<Lot> {
  const raw = await apiRequest<unknown>(`/lots/${lotId}`, {
    method: "PATCH",
    json: payload,
    withCsrf: true,
  });
  return lotSchema.parse(raw);
}

export async function archiveLot(lotId: string): Promise<Lot> {
  const raw = await apiRequest<unknown>(`/lots/${lotId}/archive`, {
    method: "POST",
    withCsrf: true,
  });
  return lotSchema.parse(raw);
}

export async function deleteLot(lotId: string): Promise<void> {
  await apiRequest<void>(`/lots/${lotId}`, {
    method: "DELETE",
    withCsrf: true,
  });
}

export async function fetchLotCostItems(lotId: string): Promise<CostItem[]> {
  const raw = await apiRequest<unknown[]>(`/lots/${lotId}/cost-items`);
  return raw.map((c) => costItemSchema.parse(c));
}

export async function addCostItemToLot(
  lotId: string,
  costItemId: string,
): Promise<LotCostItemRef> {
  const raw = await apiRequest<LotCostItemRef>(`/lots/${lotId}/cost-items`, {
    method: "POST",
    json: { cost_item_id: costItemId },
    withCsrf: true,
  });
  return raw;
}

export async function removeCostItemFromLot(
  lotId: string,
  costItemId: string,
): Promise<void> {
  await apiRequest<void>(`/lots/${lotId}/cost-items/${costItemId}`, {
    method: "DELETE",
    withCsrf: true,
  });
}

// --- hooks -----------------------------------------------------------------

export const lotsKey = (objectId: string, includeArchived: boolean) =>
  ["lots", objectId, includeArchived] as const;

export function useLots(
  objectId: string,
  opts: { includeArchived?: boolean } = {},
): UseQueryResult<Lot[]> {
  const includeArchived = opts.includeArchived ?? false;
  return useQuery({
    queryKey: lotsKey(objectId, includeArchived),
    queryFn: () => fetchLots(objectId, { includeArchived }),
    enabled: Boolean(objectId),
  });
}

export function useLot(lotId: string): UseQueryResult<Lot> {
  return useQuery({
    queryKey: ["lot", lotId] as const,
    queryFn: () => fetchLot(lotId),
    enabled: Boolean(lotId),
  });
}

export function useLotCostItems(lotId: string): UseQueryResult<CostItem[]> {
  return useQuery({
    queryKey: ["lot-cost-items", lotId] as const,
    queryFn: () => fetchLotCostItems(lotId),
    enabled: Boolean(lotId),
  });
}

export function useCreateLot(
  objectId: string,
): UseMutationResult<Lot, Error, LotCreate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: LotCreate) => createLot(objectId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["lots", objectId] });
    },
  });
}

export function useUpdateLot(
  lotId: string,
): UseMutationResult<Lot, Error, LotUpdate> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: LotUpdate) => updateLot(lotId, payload),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["lots", data.object_id] });
      void qc.invalidateQueries({ queryKey: ["lot", lotId] });
    },
  });
}

export function useArchiveLot(
  lotId: string,
): UseMutationResult<Lot, Error, void> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => archiveLot(lotId),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ["lots", data.object_id] });
      void qc.invalidateQueries({ queryKey: ["lot", lotId] });
    },
  });
}

export function useDeleteLot(
  lotId: string,
  objectId: string,
): UseMutationResult<void, Error, void> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => deleteLot(lotId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["lots", objectId] });
    },
  });
}

export function useAddCostItemToLot(
  lotId: string,
): UseMutationResult<LotCostItemRef, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (costItemId: string) => addCostItemToLot(lotId, costItemId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["lot-cost-items", lotId] });
      void qc.invalidateQueries({ queryKey: ["lot", lotId] });
    },
  });
}

export function useRemoveCostItemFromLot(
  lotId: string,
): UseMutationResult<void, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (costItemId: string) => removeCostItemFromLot(lotId, costItemId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["lot-cost-items", lotId] });
      void qc.invalidateQueries({ queryKey: ["lot", lotId] });
    },
  });
}
