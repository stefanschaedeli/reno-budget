/**
 * Wire-format types and Zod schemas for the cost-items domain.
 *
 * Mirrors backend/app/schemas/cost_item.py (Phase 3 backend agent).
 * Monetary amounts are exchanged as **strings** to avoid IEEE-754 drift
 * for CHF values with two decimal places. Formatting for display happens
 * in components via {@link formatChf}.
 *
 * The {@link CostItemAllocation} sum invariant — 1000‰ per cost item —
 * is mirrored on the backend by `services/allocations.py`; the client
 * checks it for UX feedback only and the server remains authoritative.
 */
import { z } from "zod";

export const COST_STATUSES = [
  "idea",
  "planned",
  "in_progress",
  "completed",
  "cancelled",
] as const;
export type CostStatus = (typeof COST_STATUSES)[number];

export const COST_PRIORITIES = ["low", "med", "high", "urgent"] as const;
export type CostPriority = (typeof COST_PRIORITIES)[number];

export const COST_SCOPES = ["shared", "unit"] as const;
export type CostScope = (typeof COST_SCOPES)[number];

/**
 * Decimal-string regex for non-negative CHF amounts with up to 2 decimals.
 *
 * The pattern is anchored and uses a non-capturing group; both `\d+`
 * quantifiers are bounded by the surrounding anchors so backtracking
 * is linear (no catastrophic-backtracking risk).
 */
// eslint-disable-next-line security/detect-unsafe-regex -- bounded, anchored decimal
const CHF_RE = /^\d+(?:\.\d{1,2})?$/;
const chfString = z
  .string()
  .regex(CHF_RE, "Betrag muss eine Zahl mit max. 2 Nachkommastellen sein");

export const costItemAllocationSchema = z.object({
  unit_id: z.string().uuid(),
  share_permille: z.number().int().min(0).max(1000),
});
export type CostItemAllocation = z.infer<typeof costItemAllocationSchema>;

/** One BKP-share row on a cost item (Phase 11A: multi-BKP allocations). */
export const bkpAllocationItemSchema = z.object({
  bkp_code: z.string().min(1),
  share_permille: z.number().int().min(0).max(1000),
});
export type BkpAllocationItem = z.infer<typeof bkpAllocationItemSchema>;

export const costItemSchema = z.object({
  id: z.string().uuid(),
  object_id: z.string().uuid(),
  // Phase 11A: nullable. Items may instead carry bkp_allocations, or be uncategorised.
  bkp_code: z.string().nullable(),
  project_id: z.string().uuid().nullable().optional(),
  npk_code: z.string().nullable(),
  title: z.string(),
  description: z.string().nullable(),
  status: z.enum(COST_STATUSES),
  priority: z.enum(COST_PRIORITIES),
  planned_year: z.number().int().nullable(),
  planned_amount_chf: chfString,
  actual_amount_chf: chfString.nullable(),
  actual_date: z.string().nullable(),
  lifespan_years: z.number().int().nullable(),
  warranty_until: z.string().nullable(),
  scope: z.enum(COST_SCOPES),
  created_by: z.string().uuid().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  allocations: z.array(costItemAllocationSchema),
  bkp_allocations: z.array(bkpAllocationItemSchema).default([]),
  // Phase 11A: populated only when the list endpoint is called with
  // ``?include_tag_ids=true``; ``null`` means "not requested" (NOT "no tags").
  tag_ids: z.array(z.string().uuid()).nullable().optional(),
  // Phase 11B: same pattern for lot membership ids.
  lot_ids: z.array(z.string().uuid()).nullable().optional(),
});
export type CostItem = z.infer<typeof costItemSchema>;

/**
 * Input schema for create/update. The shape mirrors the backend's
 * Pydantic schema; client-side checks are best-effort.
 *
 * - `actual_amount_chf` is optional (only set once work is done).
 * - At least one of `planned_amount_chf` / `actual_amount_chf` must be
 *   present to make the item useful (matches backend invariant).
 * - For `scope === "unit"`, `allocations` must be non-empty.
 * - Allocation `share_permille` values must sum to exactly 1000.
 */
export const costItemInputSchema = z
  .object({
    // Phase 11A: nullable singleton. If null, item must either carry
    // bkp_allocations or be intentionally uncategorised.
    bkp_code: z.string().min(1).nullable(),
    project_id: z.string().uuid().nullable().optional(),
    bkp_allocations: z.array(bkpAllocationItemSchema).optional(),
    npk_code: z.string().nullable().optional(),
    title: z.string().min(1, "Titel erforderlich").max(200),
    description: z.string().max(2000).nullable().optional(),
    status: z.enum(COST_STATUSES),
    priority: z.enum(COST_PRIORITIES),
    planned_year: z
      .number()
      .int()
      .min(1900)
      .max(2200)
      .nullable()
      .optional(),
    planned_amount_chf: chfString.nullable().optional(),
    actual_amount_chf: chfString.nullable().optional(),
    actual_date: z.string().nullable().optional(),
    lifespan_years: z.number().int().min(0).max(200).nullable().optional(),
    warranty_until: z.string().nullable().optional(),
    scope: z.enum(COST_SCOPES),
    allocations: z.array(costItemAllocationSchema),
  })
  .superRefine((data, ctx) => {
    if (!data.planned_amount_chf && !data.actual_amount_chf) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["planned_amount_chf"],
        message:
          "Mindestens ein Betrag (geplant oder effektiv) ist erforderlich",
      });
    }
    if (data.scope === "unit" && data.allocations.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["allocations"],
        message:
          "Für 'Pro Einheit' ist mindestens eine Zuteilung erforderlich",
      });
    }
    const sum = data.allocations.reduce(
      (acc, a) => acc + a.share_permille,
      0,
    );
    if (data.allocations.length > 0 && sum !== 1000) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["allocations"],
        message: `Summe der Anteile muss 1000‰ ergeben (aktuell ${sum}‰)`,
      });
    }
    // Phase 11A: multi-BKP allocations XOR singleton bkp_code.
    const bkpAllocs = data.bkp_allocations ?? [];
    if (bkpAllocs.length > 0) {
      const bsum = bkpAllocs.reduce((acc, a) => acc + a.share_permille, 0);
      if (bsum !== 1000) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["bkp_allocations"],
          message: `Summe der BKP-Anteile muss 1000‰ ergeben (aktuell ${bsum}‰)`,
        });
      }
      if (data.bkp_code) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["bkp_allocations"],
          message:
            "Entweder einzelner BKP-Code oder mehrere BKP-Anteile — nicht beides.",
        });
      }
    }
  });
export type CostItemInput = z.infer<typeof costItemInputSchema>;

/** Filter set for the list/board view. All optional; combined with AND. */
export interface CostItemFilters {
  status?: CostStatus[] | undefined;
  priority?: CostPriority[] | undefined;
  planned_year?: number | null | undefined;
  unit_id?: string | null | undefined;
  bkp_prefix?: string | null | undefined;
  project_id?: string | null | undefined;
  /** Tag-id OR filter — multiple tag ids are OR-ed by the backend. */
  tag_ids?: string[] | undefined;
  /** Phase 11B: filter to cost items that are a member of this lot. */
  lot_id?: string | null | undefined;
  q?: string | null | undefined;
  /** When true the list includes per-item ``tag_ids`` (one extra batched query). */
  include_tag_ids?: boolean | undefined;
  /** When true the list includes per-item ``lot_ids`` (one extra batched query). */
  include_lot_ids?: boolean | undefined;
}

// --- BKP catalog -----------------------------------------------------------

export const bkpCodeSchema = z.object({
  code: z.string(),
  parent_code: z.string().nullable(),
  level: z.number().int(),
  label_de: z.string(),
  description: z.string().nullable(),
  is_seed: z.boolean(),
});
export type BkpCode = z.infer<typeof bkpCodeSchema>;

export interface BkpTreeNode extends BkpCode {
  children: BkpTreeNode[];
}

export const bkpTreeNodeSchema: z.ZodType<BkpTreeNode> = bkpCodeSchema.extend({
  children: z.lazy(() => z.array(bkpTreeNodeSchema)),
});

// --- Formatting helpers ----------------------------------------------------

const CHF_FMT = new Intl.NumberFormat("de-CH", {
  style: "currency",
  currency: "CHF",
});

/**
 * Formats a CHF decimal string as Swiss currency. Returns "—" for null /
 * empty input so it composes cleanly inside tables.
 */
export function formatChf(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return CHF_FMT.format(n);
}
