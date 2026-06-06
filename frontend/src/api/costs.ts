/**
 * Cost-items API client + TanStack Query hooks.
 *
 * Decimal handling: `planned_amount_chf` and `actual_amount_chf` are sent
 * and received as **strings** (e.g. `"12345.67"`) to avoid float drift.
 * Components format them for display via {@link formatChf} from
 * `features/costs/types`.
 *
 * Mutating endpoints attach the CSRF double-submit header via the shared
 * client wrapper (`withCsrf: true`); the backend enforces it.
 *
 * Optimistic status updates: `useUpdateCostItemStatus` is used by the
 * board's drag-and-drop. We optimistically patch the cached list and
 * roll back on error so the UI stays responsive on slow links.
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
  type CostItem,
  type CostItemFilters,
  type CostItemInput,
  type CostStatus,
  costItemSchema,
} from "@/features/costs/types";

function filtersToQuery(filters: CostItemFilters): string {
  const params = new URLSearchParams();
  if (filters.status && filters.status.length > 0) {
    for (const s of filters.status) params.append("status", s);
  }
  if (filters.priority && filters.priority.length > 0) {
    for (const p of filters.priority) params.append("priority", p);
  }
  if (filters.planned_year !== null && filters.planned_year !== undefined) {
    params.set("planned_year", String(filters.planned_year));
  }
  if (filters.unit_id) params.set("unit_id", filters.unit_id);
  if (filters.bkp_prefix) params.set("bkp_prefix", filters.bkp_prefix);
  if (filters.q) params.set("q", filters.q);
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchCostItems(
  objectId: string,
  filters: CostItemFilters,
): Promise<CostItem[]> {
  const raw = await apiRequest<unknown[]>(
    `/objects/${objectId}/cost-items${filtersToQuery(filters)}`,
  );
  return raw.map((c) => costItemSchema.parse(c));
}

export async function createCostItem(
  objectId: string,
  payload: CostItemInput,
): Promise<CostItem> {
  const raw = await apiRequest<unknown>(`/objects/${objectId}/cost-items`, {
    method: "POST",
    json: payload,
    withCsrf: true,
  });
  return costItemSchema.parse(raw);
}

export async function updateCostItem(
  objectId: string,
  costItemId: string,
  payload: CostItemInput,
): Promise<CostItem> {
  const raw = await apiRequest<unknown>(
    `/objects/${objectId}/cost-items/${costItemId}`,
    {
      method: "PUT",
      json: payload,
      withCsrf: true,
    },
  );
  return costItemSchema.parse(raw);
}

export async function patchCostItemStatus(
  objectId: string,
  costItemId: string,
  status: CostStatus,
): Promise<CostItem> {
  const raw = await apiRequest<unknown>(
    `/objects/${objectId}/cost-items/${costItemId}`,
    {
      method: "PATCH",
      json: { status },
      withCsrf: true,
    },
  );
  return costItemSchema.parse(raw);
}

export async function deleteCostItem(
  objectId: string,
  costItemId: string,
): Promise<void> {
  await apiRequest<void>(`/objects/${objectId}/cost-items/${costItemId}`, {
    method: "DELETE",
    withCsrf: true,
  });
}

// --- hooks -----------------------------------------------------------------

/** Cache key for a filtered cost-items list. */
export const costItemsKey = (
  objectId: string,
  filters: CostItemFilters,
): readonly unknown[] => ["cost-items", objectId, filters];

export function useCostItems(
  objectId: string,
  filters: CostItemFilters,
): UseQueryResult<CostItem[]> {
  return useQuery({
    queryKey: costItemsKey(objectId, filters),
    queryFn: () => fetchCostItems(objectId, filters),
    enabled: Boolean(objectId),
  });
}

export function useCreateCostItem(
  objectId: string,
): UseMutationResult<CostItem, Error, CostItemInput> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CostItemInput) => createCostItem(objectId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["cost-items", objectId] });
    },
  });
}

export function useUpdateCostItem(
  objectId: string,
  costItemId: string,
): UseMutationResult<CostItem, Error, CostItemInput> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CostItemInput) =>
      updateCostItem(objectId, costItemId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["cost-items", objectId] });
    },
  });
}

export function useDeleteCostItem(
  objectId: string,
): UseMutationResult<void, Error, string> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (costItemId: string) => deleteCostItem(objectId, costItemId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["cost-items", objectId] });
    },
  });
}

interface StatusUpdateVars {
  costItemId: string;
  status: CostStatus;
}

interface StatusUpdateContext {
  snapshots: Array<[readonly unknown[], CostItem[] | undefined]>;
}

/**
 * Optimistic status update used by the kanban board's drag-and-drop.
 *
 * On mutate: every cached `cost-items` query for the object is patched
 * in-place; the previous values are snapshotted so we can roll back on
 * error. On success: queries are invalidated to pick up server truth.
 */
export function useUpdateCostItemStatus(
  objectId: string,
): UseMutationResult<CostItem, Error, StatusUpdateVars, StatusUpdateContext> {
  const qc = useQueryClient();
  return useMutation<CostItem, Error, StatusUpdateVars, StatusUpdateContext>({
    mutationFn: ({ costItemId, status }) =>
      patchCostItemStatus(objectId, costItemId, status),
    onMutate: ({ costItemId, status }) => {
      const queries = qc.getQueriesData<CostItem[]>({
        queryKey: ["cost-items", objectId],
      });
      const snapshots: StatusUpdateContext["snapshots"] = [];
      for (const [key, data] of queries) {
        snapshots.push([key, data]);
        if (!data) continue;
        qc.setQueryData<CostItem[]>(
          key,
          data.map((c) => (c.id === costItemId ? { ...c, status } : c)),
        );
      }
      return { snapshots };
    },
    onError: (_err, _vars, ctx) => {
      if (!ctx) return;
      for (const [key, data] of ctx.snapshots) {
        qc.setQueryData(key, data);
      }
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ["cost-items", objectId] });
    },
  });
}
