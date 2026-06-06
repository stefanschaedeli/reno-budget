/**
 * Wire-format types for the objects domain.
 *
 * Keep these in lock-step with backend/app/schemas/object.py. If a field
 * drifts, the easiest tell is a runtime Zod parse failure on the API
 * response — the form-level Zod schemas in this folder are the canonical
 * client-side contract.
 */
import { z } from "zod";

export type ObjectType = "sfh" | "mfh";
export type ObjectRole = "owner" | "editor" | "viewer";

export const unitSchema = z.object({
  id: z.string().uuid(),
  object_id: z.string().uuid(),
  label: z.string(),
  wertquote_permille: z.number().int().min(0).max(1000),
  area_m2: z.number().int().nullable(),
});
export type Unit = z.infer<typeof unitSchema>;

export const objectPublicSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  address: z.string().nullable(),
  year_built: z.number().int().nullable(),
  type: z.enum(["sfh", "mfh"]),
  planning_horizon_years: z.number().int(),
  created_at: z.string(),
});
export type ObjectPublic = z.infer<typeof objectPublicSchema>;

export const objectDetailSchema = objectPublicSchema.extend({
  units: z.array(unitSchema),
});
export type ObjectDetail = z.infer<typeof objectDetailSchema>;

/**
 * Form input schema for creating an object. Note: backend re-checks
 * Wertquoten sum and SFH-shape; this client-side check is for UX only.
 */
export const unitInputSchema = z.object({
  label: z.string().min(1).max(64),
  wertquote_permille: z.number().int().min(0).max(1000),
  area_m2: z.number().int().min(0).nullable().optional(),
});
export type UnitInput = z.infer<typeof unitInputSchema>;

export const objectCreateSchema = z
  .object({
    name: z.string().min(1).max(120),
    address: z.string().max(255).nullable().optional(),
    year_built: z.number().int().min(1500).max(2100).nullable().optional(),
    type: z.enum(["sfh", "mfh"]),
    planning_horizon_years: z.number().int().min(1).max(100).default(30),
    units: z.array(unitInputSchema).min(1),
  })
  .superRefine((data, ctx) => {
    const sum = data.units.reduce((acc, u) => acc + u.wertquote_permille, 0);
    if (sum !== 1000) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["units"],
        message: `Summe der Wertquoten muss 1000‰ ergeben (aktuell ${sum}‰)`,
      });
    }
    if (
      data.type === "sfh" &&
      (data.units.length !== 1 || data.units[0]!.wertquote_permille !== 1000)
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["units"],
        message: "Einfamilienhaus muss genau eine Einheit mit 1000‰ enthalten",
      });
    }
  });
export type ObjectCreateInput = z.infer<typeof objectCreateSchema>;
