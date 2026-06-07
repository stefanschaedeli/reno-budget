/**
 * Wire-format types and Zod schemas for the Lots domain (Phase 11B).
 *
 * Mirrors backend/app/schemas/lot.py. A Lot is a cross-project bidding
 * package scoped to one object; archived lots are soft-hidden by default
 * in list endpoints. Membership (cost items) is managed via dedicated
 * endpoints, not by the lot CRUD payloads.
 */
import { z } from "zod";

export const LOT_STATUSES = [
  "draft",
  "tendering",
  "awarded",
  "cancelled",
  "completed",
] as const;
export type LotStatus = (typeof LOT_STATUSES)[number];

export const lotSchema = z.object({
  id: z.string().uuid(),
  object_id: z.string().uuid(),
  name: z.string(),
  description: z.string().nullable(),
  status: z.enum(LOT_STATUSES),
  tender_deadline: z.string().nullable(),
  awarded_quote_id: z.string().uuid().nullable(),
  archived_at: z.string().nullable(),
  created_by: z.string().uuid().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  cost_item_count: z.number().int().default(0),
  cost_item_ids: z.array(z.string().uuid()).nullable().optional(),
});
export type Lot = z.infer<typeof lotSchema>;

export const lotCreateSchema = z.object({
  name: z.string().min(1, "Name erforderlich").max(160),
  description: z.string().max(2000).nullable().optional(),
  status: z.enum(LOT_STATUSES).default("draft"),
  tender_deadline: z.string().nullable().optional(),
});
export type LotCreate = z.infer<typeof lotCreateSchema>;

export const lotUpdateSchema = lotCreateSchema.partial();
export type LotUpdate = z.infer<typeof lotUpdateSchema>;

export interface LotCostItemRef {
  lot_id: string;
  cost_item_id: string;
}
