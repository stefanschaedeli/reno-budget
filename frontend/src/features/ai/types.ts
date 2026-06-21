/**
 * Zod schemas + types for the AI Project Assistant, mirroring the backend
 * structured-output and DTO models in `backend/app/schemas/ai.py`.
 */
import { z } from "zod";

const chfString = z.string().regex(/^-?\d+(?:\.\d{1,2})?$/);

export const AI_STEPS = [
  "classify",
  "question",
  "describe",
  "estimate",
  "bkp_scope",
] as const;
export type AiStep = (typeof AI_STEPS)[number];

export const confidenceSchema = z.enum(["low", "medium", "high"]);
export type Confidence = z.infer<typeof confidenceSchema>;

export const questionTypeSchema = z.enum(["number", "select", "text", "boolean"]);
export type QuestionType = z.infer<typeof questionTypeSchema>;

export const generatedQuestionSchema = z.object({
  key: z.string(),
  label: z.string(),
  type: questionTypeSchema,
  unit: z.string().nullable().optional(),
  help: z.string().nullable().optional(),
  required: z.boolean().default(true),
  min: z.number().nullable().optional(),
  max: z.number().nullable().optional(),
  options: z.array(z.string()).nullable().optional(),
  maps_to: z.string().nullable().optional(),
});
export type GeneratedQuestion = z.infer<typeof generatedQuestionSchema>;

export const questionSetSchema = z.object({
  questions: z.array(generatedQuestionSchema),
});

export const estimateLineItemSchema = z.object({
  label: z.string(),
  amount_chf: chfString,
  assumptions: z.string(),
  confidence: confidenceSchema,
});
export type EstimateLineItem = z.infer<typeof estimateLineItemSchema>;

export const estimateSchema = z.object({
  currency: z.string().default("CHF"),
  total_chf: chfString,
  line_items: z.array(estimateLineItemSchema),
  notes: z.string().nullable().optional(),
});

export const bkpPositionSchema = z.object({
  bkp_code: z.string(),
  title: z.string(),
  in_scope: z.array(z.string()),
  out_of_scope: z.array(z.string()),
  estimated_amount_chf: chfString,
  assumptions: z.string(),
  confidence: confidenceSchema,
});
export type BkpPosition = z.infer<typeof bkpPositionSchema>;

export const bkpScopeSchema = z.object({
  positions: z.array(bkpPositionSchema),
});

export const validationSeveritySchema = z.enum(["info", "warning", "error"]);

export const validationFindingSchema = z.object({
  layer: z.number().int(),
  severity: validationSeveritySchema,
  message: z.string(),
  target: z.string().nullable().optional(),
});
export type ValidationFinding = z.infer<typeof validationFindingSchema>;

export const validationReportSchema = z.object({
  ok: z.boolean(),
  findings: z.array(validationFindingSchema).default([]),
});
export type ValidationReport = z.infer<typeof validationReportSchema>;

export const artifactSchema = z.object({
  id: z.string(),
  session_id: z.string(),
  step: z.enum(AI_STEPS),
  status: z.enum(["draft", "accepted", "discarded"]),
  output: z.record(z.unknown()),
  validation: z.record(z.unknown()),
  created_at: z.string(),
  updated_at: z.string(),
});
export type AiArtifact = z.infer<typeof artifactSchema>;

export const sessionSchema = z.object({
  id: z.string(),
  object_id: z.string(),
  project_id: z.string(),
  status: z.enum(["active", "completed", "abandoned"]),
  project_type: z.string().nullable(),
  answers: z.record(z.unknown()),
  created_at: z.string(),
  updated_at: z.string(),
  artifacts: z.array(artifactSchema).default([]),
});
export type AiSession = z.infer<typeof sessionSchema>;
