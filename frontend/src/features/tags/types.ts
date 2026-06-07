/**
 * Wire-format types and Zod schemas for the Tags domain (Phase 11A).
 *
 * Tags are per-object `key=value` labels with an optional hex colour.
 * They attach polymorphically to projects or cost items via
 * TagAssignment rows (Phase B will add `lot`).
 */
import { z } from "zod";

export const TAG_TARGET_TYPES = ["project", "cost_item", "lot"] as const;
export type TagTargetType = (typeof TAG_TARGET_TYPES)[number];

const HEX_COLOR_RE = /^#[0-9a-fA-F]{6}$/;

export const tagSchema = z.object({
  id: z.string().uuid(),
  object_id: z.string().uuid(),
  key: z.string(),
  value: z.string(),
  color: z.string().nullable(),
  created_at: z.string(),
});
export type Tag = z.infer<typeof tagSchema>;

export const tagCreateSchema = z.object({
  key: z.string().min(1, "Key erforderlich").max(64),
  value: z.string().min(1, "Wert erforderlich").max(64),
  color: z
    .string()
    .regex(HEX_COLOR_RE, "Farbe muss ein Hex-Wert wie '#aabbcc' sein")
    .nullable()
    .optional(),
});
export type TagCreate = z.infer<typeof tagCreateSchema>;

export const tagUpdateSchema = tagCreateSchema.partial();
export type TagUpdate = z.infer<typeof tagUpdateSchema>;

export const tagAssignmentSchema = z.object({
  tag_id: z.string().uuid(),
  target_type: z.enum(TAG_TARGET_TYPES),
  target_id: z.string().uuid(),
});
export type TagAssignment = z.infer<typeof tagAssignmentSchema>;
