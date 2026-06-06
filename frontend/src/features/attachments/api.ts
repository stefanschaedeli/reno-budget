/**
 * Attachments API client (Phase 6).
 *
 * Uploads use `XMLHttpRequest` instead of `fetch` because we need progress
 * events (the `fetch` API does not surface upload progress in any browser).
 * The CSRF double-submit header is read from the cookie on the fly to match
 * the convention in `api/client.ts`.
 *
 * Downloads are handled by setting `window.location` / `<a download>` — the
 * backend already streams with `Content-Disposition: attachment`.
 */
import { apiRequest } from "@/api/client";
import {
  type Attachment,
  type AttachmentTargetType,
  attachmentSchema,
} from "./types";

const API_PREFIX = "/api/v1";

function targetPath(targetType: AttachmentTargetType, targetId: string): string {
  return targetType === "cost_item"
    ? `${API_PREFIX}/cost-items/${targetId}/attachments`
    : `${API_PREFIX}/objects/${targetId}/attachments`;
}

function readCsrfCookie(): string {
  const m = document.cookie.match(/(?:^|;\s*)reno_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]!) : "";
}

export async function listAttachments(
  targetType: AttachmentTargetType,
  targetId: string,
): Promise<Attachment[]> {
  const path =
    targetType === "cost_item"
      ? `/cost-items/${targetId}/attachments`
      : `/objects/${targetId}/attachments`;
  const raw = await apiRequest<unknown[]>(path);
  return raw.map((r) => attachmentSchema.parse(r));
}

export interface UploadProgressEvent {
  /** Loaded bytes. */
  loaded: number;
  /** Total bytes if known, else `null`. */
  total: number | null;
  /** 0..1 if total is known, else `null`. */
  fraction: number | null;
}

export interface UploadOptions {
  /** Bearer access token. */
  accessToken: string;
  /** Called on every `progress` event of the upload phase. */
  onProgress?: (e: UploadProgressEvent) => void;
  /** Optional abort signal. */
  signal?: AbortSignal;
}

/**
 * Upload a single file with progress reporting.
 *
 * Resolves with the parsed `Attachment`; rejects with an `Error` carrying the
 * server's detail message (or a generic translation key if the body wasn't
 * JSON, e.g. a 413 from an upstream proxy).
 */
export function uploadAttachment(
  targetType: AttachmentTargetType,
  targetId: string,
  file: File,
  opts: UploadOptions,
): Promise<Attachment> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", targetPath(targetType, targetId), true);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Authorization", `Bearer ${opts.accessToken}`);
    xhr.setRequestHeader("X-CSRF-Token", readCsrfCookie());
    xhr.setRequestHeader("Accept", "application/json");

    if (opts.onProgress) {
      xhr.upload.addEventListener("progress", (ev) => {
        opts.onProgress!({
          loaded: ev.loaded,
          total: ev.lengthComputable ? ev.total : null,
          fraction: ev.lengthComputable && ev.total > 0 ? ev.loaded / ev.total : null,
        });
      });
    }

    if (opts.signal) {
      // Abort the XHR if the consumer cancels; do not throw here, the
      // `abort` handler below produces the rejection.
      opts.signal.addEventListener("abort", () => xhr.abort());
    }

    xhr.addEventListener("load", () => {
      const status = xhr.status;
      let body: unknown;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        body = xhr.responseText;
      }
      if (status >= 200 && status < 300) {
        try {
          resolve(attachmentSchema.parse(body));
        } catch (e) {
          reject(e instanceof Error ? e : new Error("attachments.errors.parse"));
        }
      } else {
        const detail =
          (body as { detail?: unknown })?.detail ??
          (typeof body === "string" ? body : "attachments.errors.uploadFailed");
        const err = new Error(typeof detail === "string" ? detail : "attachments.errors.uploadFailed");
        (err as { status?: number }).status = status;
        reject(err);
      }
    });
    xhr.addEventListener("error", () => {
      reject(new Error("attachments.errors.network"));
    });
    xhr.addEventListener("abort", () => {
      reject(new Error("attachments.errors.aborted"));
    });

    const fd = new FormData();
    fd.append("file", file, file.name);
    xhr.send(fd);
  });
}

export async function deleteAttachment(attachmentId: string): Promise<void> {
  await apiRequest<void>(`/attachments/${attachmentId}`, {
    method: "DELETE",
    withCsrf: true,
  });
}

/** Build the absolute download URL used by `<a href>` and `window.open`. */
export function downloadUrl(attachmentId: string): string {
  return `${API_PREFIX}/attachments/${attachmentId}/download`;
}
