import { ApiError } from "@/api/client";

/**
 * Best-effort extraction of a human-readable message from an unknown error.
 * Used for toast feedback on mutations — falls back to a caller-provided
 * default when nothing useful can be pulled from the error object.
 */
export function apiErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    const d = err.detail;
    if (typeof d === "string" && d.length > 0) return d;
    if (d && typeof d === "object" && "detail" in d) {
      const inner = d.detail;
      if (typeof inner === "string" && inner.length > 0) return inner;
    }
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
