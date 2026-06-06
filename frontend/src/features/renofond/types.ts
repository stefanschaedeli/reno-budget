/**
 * Zod types matching the backend Renofond schemas (Phase 5).
 *
 * Money values arrive as strings (Decimal serialisation) to avoid
 * float drift; we keep them as strings in the type system and parse
 * only when rendering a chart bar height.
 */
import { z } from "zod";

export const OBJECT_ROLES = ["owner", "editor", "viewer"] as const;
export type ObjectRole = (typeof OBJECT_ROLES)[number];

export const projectionRowSchema = z.object({
  year: z.number().int(),
  required_contribution_chf: z.string(),
  actual_contribution_chf: z.string(),
  planned_spend_chf: z.string(),
  balance_chf: z.string(),
  cumulative_planned_chf: z.string(),
  is_underfunded: z.boolean(),
});
export type ProjectionRow = z.infer<typeof projectionRowSchema>;

export const underfundingYearSchema = z.object({
  year: z.number().int(),
  shortfall_chf: z.string(),
});
export type UnderfundingYear = z.infer<typeof underfundingYearSchema>;

export const projectionResponseSchema = z.object({
  object_id: z.string(),
  current_year: z.number().int(),
  horizon_until_year: z.number().int(),
  inflation_rate_percent: z.string(),
  initial_reserve_chf: z.string(),
  required_per_year_chf: z.string(),
  rows: z.array(projectionRowSchema),
  underfunding_years: z.array(underfundingYearSchema),
  scope_pro_rated: z.boolean(),
});
export type ProjectionResponse = z.infer<typeof projectionResponseSchema>;

export const contributionSchema = z.object({
  id: z.string(),
  object_id: z.string(),
  year: z.number().int(),
  amount_chf: z.string(),
  note: z.string().nullable(),
  created_at: z.string(),
});
export type Contribution = z.infer<typeof contributionSchema>;

export const contributionListSchema = z.object({
  items: z.array(contributionSchema),
  my_role: z.enum(OBJECT_ROLES),
});
export type ContributionList = z.infer<typeof contributionListSchema>;

export interface ContributionCreate {
  year: number;
  amount_chf: string;
  note?: string | null;
}
