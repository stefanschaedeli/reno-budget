/**
 * Zod schema + types for the attachments domain (Phase 6).
 *
 * The shape mirrors `AttachmentRead` on the backend exactly. Decimals and
 * other complex types don't appear here — attachments are pure metadata.
 */
import { z } from "zod";

export const attachmentSchema = z.object({
  id: z.string().uuid(),
  target_type: z.enum(["cost_item", "object"]),
  target_id: z.string().uuid(),
  sha256: z.string().length(64),
  filename: z.string(),
  mime: z.string(),
  size_bytes: z.number().int().nonnegative(),
  uploaded_by: z.string().uuid().nullable(),
  created_at: z.string(), // ISO 8601
});

export type Attachment = z.infer<typeof attachmentSchema>;

export type AttachmentTargetType = "cost_item" | "object";

/** Human-readable byte size — "12,3 KB", "4,5 MB". German formatting. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"] as const;
  let value = bytes / 1024;
  let unit: (typeof units)[number] = "KB";
  for (const candidate of units.slice(1)) {
    if (value < 1024) break;
    value /= 1024;
    unit = candidate;
  }
  // de-CH formatting: comma decimal separator, one fractional digit.
  return `${value.toLocaleString("de-CH", { maximumFractionDigits: 1 })} ${unit}`;
}
