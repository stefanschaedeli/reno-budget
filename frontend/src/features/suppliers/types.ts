/**
 * Wire-format types and Zod schemas for the Suppliers domain (Phase 11C).
 *
 * Mirrors backend/app/schemas/supplier.py. A Supplier is a per-object
 * address-book entry; archived rows are soft-hidden by default in list
 * endpoints.
 */
import { z } from "zod";

export const supplierSchema = z.object({
  id: z.string().uuid(),
  object_id: z.string().uuid(),
  name: z.string(),
  contact_email: z.string().nullable(),
  contact_phone: z.string().nullable(),
  address: z.string().nullable(),
  notes: z.string().nullable(),
  archived_at: z.string().nullable(),
  created_by: z.string().uuid().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Supplier = z.infer<typeof supplierSchema>;

export const supplierCreateSchema = z.object({
  name: z.string().min(1, "Name erforderlich").max(160),
  contact_email: z.string().email().nullable().optional(),
  contact_phone: z.string().max(40).nullable().optional(),
  address: z.string().max(255).nullable().optional(),
  notes: z.string().nullable().optional(),
});
export type SupplierCreate = z.infer<typeof supplierCreateSchema>;

export const supplierUpdateSchema = supplierCreateSchema.partial();
export type SupplierUpdate = z.infer<typeof supplierUpdateSchema>;
