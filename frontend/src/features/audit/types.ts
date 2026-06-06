/**
 * Audit event types (Phase 7).
 *
 * Mirrors `app.schemas.audit.AuditEventRead` + `AuditEventPage` from the
 * backend. The action set is open-ended (string) but the most common
 * verbs are listed under `audit.actions.<verb>` in the i18n catalog so
 * the UI shows a human-readable verb instead of the raw machine string.
 */
import { z } from "zod";

export const auditEventSchema = z.object({
  id: z.string().uuid(),
  created_at: z.string(),
  actor_user_id: z.string().uuid().nullable(),
  actor_email: z.string(),
  action: z.string(),
  object_id: z.string().uuid().nullable(),
  target_type: z.string().nullable(),
  target_id: z.string().uuid().nullable(),
  summary: z.string(),
  payload: z.record(z.unknown()).nullable(),
  ip_address: z.string().nullable(),
  user_agent: z.string().nullable(),
});

export type AuditEvent = z.infer<typeof auditEventSchema>;

export const auditPageSchema = z.object({
  items: z.array(auditEventSchema),
  next_before: z.string().nullable(),
});

export type AuditPage = z.infer<typeof auditPageSchema>;
