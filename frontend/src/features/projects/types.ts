/**
 * Wire-format types and Zod schemas for the Projects domain (Phase 11A).
 *
 * Mirrors backend/app/schemas/project.py. A Project groups cost items
 * within a single object; archived projects are soft-hidden by default in
 * list endpoints.
 */
import { z } from "zod";

export const PROJECT_STATUSES = [
  "idea",
  "planned",
  "in_progress",
  "completed",
  "cancelled",
] as const;
export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

export const projectSchema = z.object({
  id: z.string().uuid(),
  object_id: z.string().uuid(),
  name: z.string(),
  description: z.string().nullable(),
  status: z.enum(PROJECT_STATUSES),
  planned_year: z.number().int().nullable(),
  archived_at: z.string().nullable(),
  created_by: z.string().uuid().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Project = z.infer<typeof projectSchema>;

export const projectCreateSchema = z.object({
  name: z.string().min(1, "Name erforderlich").max(160),
  description: z.string().max(2000).nullable().optional(),
  status: z.enum(PROJECT_STATUSES).default("idea"),
  planned_year: z.number().int().min(1900).max(2200).nullable().optional(),
});
export type ProjectCreate = z.infer<typeof projectCreateSchema>;

export const projectUpdateSchema = projectCreateSchema.partial();
export type ProjectUpdate = z.infer<typeof projectUpdateSchema>;
