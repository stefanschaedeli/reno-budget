/**
 * Audit-log API client (Phase 7).
 *
 * Two endpoints:
 *   - `/objects/{id}/audit` — owner-only per-object feed.
 *   - `/audit` — superuser-only global feed.
 *
 * Both return a keyset-paginated page; pass `before` from the previous
 * page's `next_before` to fetch older entries.
 */
import { apiRequest } from "@/api/client";
import { type AuditPage, auditPageSchema } from "./types";

export interface ListParams {
  limit?: number;
  before?: string | null;
}

function _query(params: ListParams): string {
  const qs = new URLSearchParams();
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  if (params.before) qs.set("before", params.before);
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export async function listObjectAudit(
  objectId: string,
  params: ListParams = {},
): Promise<AuditPage> {
  const raw = await apiRequest<unknown>(`/objects/${objectId}/audit${_query(params)}`);
  return auditPageSchema.parse(raw);
}

export async function listGlobalAudit(params: ListParams = {}): Promise<AuditPage> {
  const raw = await apiRequest<unknown>(`/audit${_query(params)}`);
  return auditPageSchema.parse(raw);
}
