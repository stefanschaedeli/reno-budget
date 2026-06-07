/**
 * Wire-format types for the budget domain (Phase 4).
 *
 * Decimal amounts stay as strings (mirroring cost-items) to avoid
 * float drift on the wire. Components format via {@link formatChf}.
 */
import { z } from "zod";

export const CONTRIBUTION_MODES = ["monthly", "yearly", "lump_sum"] as const;
export type ContributionMode = (typeof CONTRIBUTION_MODES)[number];

export const OBJECT_ROLES = ["owner", "editor", "viewer"] as const;
export type ObjectRole = (typeof OBJECT_ROLES)[number];

const chfString = z.string().regex(/^-?\d+(?:\.\d{1,2})?$/);

export const timelineRowSchema = z.object({
  year: z.number().int(),
  planned_chf: chfString,
  planned_inflated_chf: chfString,
  actual_chf: chfString,
});
export type TimelineRow = z.infer<typeof timelineRowSchema>;

export const yearDrillItemSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  bkp_code: z.string().nullable(),
  status: z.string(),
  priority: z.string(),
  planned_amount_chf: chfString.nullable(),
  actual_amount_chf: chfString.nullable(),
});
export type YearDrillItem = z.infer<typeof yearDrillItemSchema>;

/**
 * Sentinel returned by the backend's ``by_bkp_group`` map for cost items
 * whose ``bkp_code`` is NULL (and that carry no multi-BKP allocations).
 */
export const UNCATEGORISED_BKP_GROUP = "_uncat";

export const bkpGroupRowSchema = z.object({
  group: z.string(),
  label: z.string(),
  planned_chf: chfString,
  actual_chf: chfString,
});
export type BkpGroupRow = z.infer<typeof bkpGroupRowSchema>;

export const unitBreakdownRowSchema = z.object({
  unit_id: z.string().uuid(),
  label: z.string(),
  planned_chf: chfString,
  actual_chf: chfString,
});
export type UnitBreakdownRow = z.infer<typeof unitBreakdownRowSchema>;

export const statusPriorityRowSchema = z.object({
  status: z.string(),
  priority: z.string(),
  planned_chf: chfString,
  count: z.number().int(),
});
export type StatusPriorityRow = z.infer<typeof statusPriorityRowSchema>;

export const lumpSumYearSchema = z.object({
  year: z.number().int(),
  amount_chf: chfString,
});
export type LumpSumYear = z.infer<typeof lumpSumYearSchema>;

export const reservePlanSchema = z.object({
  object_id: z.string().uuid(),
  inflation_rate_percent: z.number(),
  initial_reserve_chf: chfString,
  contribution_mode: z.enum(CONTRIBUTION_MODES),
  horizon_years: z.number().int(),
  total_planned_inflated_chf: chfString,
  required_total_chf: chfString,
  /** For monthly/yearly: a single scalar. For lump_sum: see lump_sum_schedule. */
  required_contribution_chf: chfString.nullable(),
  lump_sum_schedule: z.array(lumpSumYearSchema),
  my_role: z.enum(OBJECT_ROLES),
});
export type ReservePlan = z.infer<typeof reservePlanSchema>;

export const timelineResponseSchema = z.object({
  object_id: z.string().uuid(),
  rows: z.array(timelineRowSchema),
  my_role: z.enum(OBJECT_ROLES),
  is_scoped: z.boolean(),
});
export type TimelineResponse = z.infer<typeof timelineResponseSchema>;

export const bkpBreakdownResponseSchema = z.object({
  rows: z.array(bkpGroupRowSchema),
});
export type BkpBreakdownResponse = z.infer<typeof bkpBreakdownResponseSchema>;

export const unitBreakdownResponseSchema = z.object({
  rows: z.array(unitBreakdownRowSchema),
});
export type UnitBreakdownResponse = z.infer<typeof unitBreakdownResponseSchema>;

export const statusPriorityResponseSchema = z.object({
  rows: z.array(statusPriorityRowSchema),
});
export type StatusPriorityResponse = z.infer<
  typeof statusPriorityResponseSchema
>;

export const yearDrillResponseSchema = z.object({
  year: z.number().int(),
  items: z.array(yearDrillItemSchema),
});
export type YearDrillResponse = z.infer<typeof yearDrillResponseSchema>;

export const financesObjectRowSchema = z.object({
  object_id: z.string().uuid(),
  name: z.string(),
  role: z.enum(OBJECT_ROLES),
  is_scoped: z.boolean(),
  total_planned_inflated_chf: chfString,
  total_actual_chf: chfString,
  required_per_year_chf: chfString,
});
export type FinancesObjectRow = z.infer<typeof financesObjectRowSchema>;

export const financesOverviewSchema = z.object({
  rows: z.array(financesObjectRowSchema),
});
export type FinancesOverview = z.infer<typeof financesOverviewSchema>;

export interface ObjectSettingsPatch {
  contribution_mode?: ContributionMode;
  inflation_rate_percent?: number;
  initial_reserve_chf?: string;
}
