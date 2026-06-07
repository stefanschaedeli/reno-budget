/**
 * Wire-format types and Zod schemas for the Quotes domain (Phase 11C).
 *
 * Mirrors backend/app/schemas/quote.py. The ``awarded`` status is set ONLY
 * via the dedicated award endpoint — direct create/update rejects it with
 * 422.
 */
import { z } from "zod";

export const QUOTE_STATUSES = [
  "received",
  "shortlisted",
  "rejected",
  "awarded",
] as const;
export type QuoteStatus = (typeof QUOTE_STATUSES)[number];

export const quoteSchema = z.object({
  id: z.string().uuid(),
  lot_id: z.string().uuid(),
  supplier_id: z.string().uuid(),
  amount_chf: z.string(),
  received_at: z.string(),
  valid_until: z.string().nullable(),
  notes: z.string().nullable(),
  status: z.enum(QUOTE_STATUSES),
  created_by: z.string().uuid().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Quote = z.infer<typeof quoteSchema>;

export const quoteCreateSchema = z.object({
  supplier_id: z.string().uuid(),
  amount_chf: z.string().min(1, "Betrag erforderlich"),
  received_at: z.string().min(1, "Eingangsdatum erforderlich"),
  valid_until: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
  status: z.enum(QUOTE_STATUSES).default("received"),
});
export type QuoteCreate = z.infer<typeof quoteCreateSchema>;

export const quoteUpdateSchema = quoteCreateSchema.partial();
export type QuoteUpdate = z.infer<typeof quoteUpdateSchema>;
