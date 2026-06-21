/**
 * Budget / reserve API client + TanStack Query hooks.
 *
 * All read endpoints are scoped to the current user: backend returns
 * pro-rated amounts when the user is a unit-scoped EDITOR/VIEWER, full
 * totals when the user is OWNER or has full-scope membership. We
 * surface that via `is_scoped` so the UI can badge accordingly.
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
  bkpBreakdownResponseSchema,
  financesOverviewSchema,
  reservePlanSchema,
  statusPriorityResponseSchema,
  timelineResponseSchema,
  unitBreakdownResponseSchema,
  yearDrillResponseSchema,
  type BkpBreakdownResponse,
  type FinancesOverview,
  type ObjectSettingsPatch,
  type ReservePlan,
  type StatusPriorityResponse,
  type TimelineResponse,
  type UnitBreakdownResponse,
  type YearDrillResponse,
} from "./types";

export async function fetchTimeline(
  objectId: string,
  inflated: boolean,
): Promise<TimelineResponse> {
  const raw = await apiRequest<unknown>(
    `/objects/${objectId}/budget/timeline?inflated=${inflated ? "1" : "0"}`,
  );
  return timelineResponseSchema.parse(raw);
}

export async function fetchYearDrill(
  objectId: string,
  year: number,
): Promise<YearDrillResponse> {
  const raw = await apiRequest<unknown>(
    `/objects/${objectId}/budget/timeline/${year}`,
  );
  return yearDrillResponseSchema.parse(raw);
}

export async function fetchBkpBreakdown(
  objectId: string,
  year: number | null,
): Promise<BkpBreakdownResponse> {
  const qs = year !== null ? `?year=${year}` : "";
  const raw = await apiRequest<unknown>(
    `/objects/${objectId}/budget/bkp-groups${qs}`,
  );
  return bkpBreakdownResponseSchema.parse(raw);
}

export async function fetchUnitBreakdown(
  objectId: string,
): Promise<UnitBreakdownResponse> {
  const raw = await apiRequest<unknown>(`/objects/${objectId}/budget/units`);
  return unitBreakdownResponseSchema.parse(raw);
}

export async function fetchStatusPriorityBreakdown(
  objectId: string,
): Promise<StatusPriorityResponse> {
  const raw = await apiRequest<unknown>(
    `/objects/${objectId}/budget/status-priority`,
  );
  return statusPriorityResponseSchema.parse(raw);
}

export async function fetchReservePlan(objectId: string): Promise<ReservePlan> {
  const raw = await apiRequest<unknown>(`/objects/${objectId}/budget/reserve`);
  return reservePlanSchema.parse(raw);
}

export async function patchObjectSettings(
  objectId: string,
  payload: ObjectSettingsPatch,
): Promise<ReservePlan> {
  const raw = await apiRequest<unknown>(`/objects/${objectId}`, {
    method: "PATCH",
    json: payload,
    withCsrf: true,
  });
  return reservePlanSchema.parse(raw);
}

export async function fetchFinancesOverview(): Promise<FinancesOverview> {
  const raw = await apiRequest<unknown>(`/finances`);
  return financesOverviewSchema.parse(raw);
}

// --- hooks -----------------------------------------------------------------

export const timelineKey = (objectId: string, inflated: boolean) =>
  ["budget", "timeline", objectId, inflated] as const;

export function useBudgetTimeline(
  objectId: string,
  opts: { inflated: boolean },
): UseQueryResult<TimelineResponse> {
  return useQuery({
    queryKey: timelineKey(objectId, opts.inflated),
    queryFn: () => fetchTimeline(objectId, opts.inflated),
    enabled: Boolean(objectId),
  });
}

export function useYearDrill(
  objectId: string,
  year: number | null,
): UseQueryResult<YearDrillResponse> {
  return useQuery({
    queryKey: ["budget", "year-drill", objectId, year] as const,
    queryFn: () => fetchYearDrill(objectId, year ?? 0),
    enabled: Boolean(objectId) && year !== null,
  });
}

export function useBkpBreakdown(
  objectId: string,
  year: number | null,
): UseQueryResult<BkpBreakdownResponse> {
  return useQuery({
    queryKey: ["budget", "bkp", objectId, year] as const,
    queryFn: () => fetchBkpBreakdown(objectId, year),
    enabled: Boolean(objectId),
  });
}

export function useUnitBreakdown(
  objectId: string,
): UseQueryResult<UnitBreakdownResponse> {
  return useQuery({
    queryKey: ["budget", "units", objectId] as const,
    queryFn: () => fetchUnitBreakdown(objectId),
    enabled: Boolean(objectId),
  });
}

export function useStatusPriorityBreakdown(
  objectId: string,
): UseQueryResult<StatusPriorityResponse> {
  return useQuery({
    queryKey: ["budget", "status-priority", objectId] as const,
    queryFn: () => fetchStatusPriorityBreakdown(objectId),
    enabled: Boolean(objectId),
  });
}

export function useReservePlan(objectId: string): UseQueryResult<ReservePlan> {
  return useQuery({
    queryKey: ["budget", "reserve", objectId] as const,
    queryFn: () => fetchReservePlan(objectId),
    enabled: Boolean(objectId),
  });
}

export function useFinancesOverview(): UseQueryResult<FinancesOverview> {
  return useQuery({
    queryKey: ["budget", "finances"] as const,
    queryFn: () => fetchFinancesOverview(),
  });
}

export function useUpdateObjectSettings(
  objectId: string,
): UseMutationResult<ReservePlan, Error, ObjectSettingsPatch> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ObjectSettingsPatch) =>
      patchObjectSettings(objectId, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["budget"] });
    },
  });
}
