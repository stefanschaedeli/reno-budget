/**
 * BKP catalog API client + TanStack Query hooks.
 *
 * The BKP catalog (eBKP-H) is read-only from the user's perspective for
 * Phase 3 — admin-managed extensions land later. We therefore use long
 * cache lifetimes (the catalog rarely changes).
 */
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiRequest } from "@/api/client";
import {
  type BkpCode,
  type BkpTreeNode,
  bkpCodeSchema,
  bkpTreeNodeSchema,
} from "@/features/costs/types";

const CATALOG_STALE_MS = 60 * 60 * 1000; // 1 hour

export async function fetchBkpCodes(): Promise<BkpCode[]> {
  const raw = await apiRequest<unknown[]>("/bkp-codes");
  return raw.map((c) => bkpCodeSchema.parse(c));
}

export async function fetchBkpTree(): Promise<BkpTreeNode[]> {
  const raw = await apiRequest<unknown[]>("/bkp-codes/tree");
  return raw.map((n) => bkpTreeNodeSchema.parse(n));
}

/** Flat list of all BKP codes. Cached for the session. */
export function useBkpCodes(): UseQueryResult<BkpCode[]> {
  return useQuery({
    queryKey: ["bkp-codes"],
    queryFn: fetchBkpCodes,
    staleTime: CATALOG_STALE_MS,
  });
}

/** Hierarchical BKP tree for the {@link BkpCodePicker}. */
export function useBkpTree(): UseQueryResult<BkpTreeNode[]> {
  return useQuery({
    queryKey: ["bkp-codes", "tree"],
    queryFn: fetchBkpTree,
    staleTime: CATALOG_STALE_MS,
  });
}
