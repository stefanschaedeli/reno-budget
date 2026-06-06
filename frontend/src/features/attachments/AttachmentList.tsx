import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/features/auth/AuthContext";
import {
  deleteAttachment,
  downloadUrl,
  listAttachments,
  uploadAttachment,
} from "./api";
import { type Attachment, type AttachmentTargetType, formatBytes } from "./types";

/**
 * Attachment manager bound to a single target (cost item or object).
 *
 * Features
 * --------
 * * Drag-and-drop OR file picker for uploads.
 * * Live progress bar driven by XMLHttpRequest upload events (the only API
 *   that surfaces them — `fetch` does not).
 * * Client-side size pre-check (matches the server cap) so users get
 *   instant feedback instead of waiting for a 413 round-trip.
 * * Delete confirmation, kept in-component (no modal lib).
 *
 * Security note: download links go through the FastAPI streaming endpoint
 * (`downloadUrl`), which sets `Content-Disposition: attachment`,
 * `Content-Security-Policy: default-src 'none'` and `X-Content-Type-Options:
 * nosniff`. We never embed attachments inline (no `<img src=…>`) to avoid
 * accidentally triggering renderer bugs on hostile blobs.
 */
export interface AttachmentListProps {
  targetType: AttachmentTargetType;
  targetId: string;
  /** EDITOR+ on parent object (drives upload/delete affordances). */
  canEdit: boolean;
  /** Optional override of the size cap (bytes). Defaults to 25 MiB. */
  maxBytes?: number;
}

const DEFAULT_MAX_BYTES = 25 * 1024 * 1024;

interface UploadingState {
  filename: string;
  fraction: number | null;
}

export function AttachmentList({
  targetType,
  targetId,
  canEdit,
  maxBytes = DEFAULT_MAX_BYTES,
}: AttachmentListProps): JSX.Element {
  const { t } = useTranslation();
  const { accessToken, user } = useAuth();
  const [items, setItems] = useState<Attachment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState<UploadingState | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const refresh = useCallback(async () => {
    try {
      const rows = await listAttachments(targetType, targetId);
      setItems(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("attachments.errors.loadFailed"));
    }
  }, [targetType, targetId, t]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      if (!accessToken) {
        setError(t("attachments.errors.notAuthenticated"));
        return;
      }
      for (const file of Array.from(files)) {
        if (file.size > maxBytes) {
          setError(t("attachments.errors.tooLarge", { name: file.name }));
          continue;
        }
        setError(null);
        setUploading({ filename: file.name, fraction: 0 });
        try {
          await uploadAttachment(targetType, targetId, file, {
            accessToken,
            onProgress: (e) =>
              setUploading({ filename: file.name, fraction: e.fraction }),
          });
          await refresh();
        } catch (e) {
          setError(e instanceof Error ? e.message : t("attachments.errors.uploadFailed"));
        } finally {
          setUploading(null);
        }
      }
    },
    [accessToken, maxBytes, targetType, targetId, t, refresh],
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      if (!canEdit) return;
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        void handleFiles(e.dataTransfer.files);
      }
    },
    [canEdit, handleFiles],
  );

  const onPick = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        void handleFiles(e.target.files);
        e.target.value = "";
      }
    },
    [handleFiles],
  );

  const onDelete = useCallback(
    async (id: string) => {
      try {
        await deleteAttachment(id);
        setConfirmId(null);
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : t("attachments.errors.deleteFailed"));
      }
    },
    [refresh, t],
  );

  return (
    <section aria-label={t("attachments.title")} className="space-y-3">
      <header className="flex items-center justify-between">
        <h3 className="text-lg font-medium">{t("attachments.title")}</h3>
        {canEdit && (
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
            onClick={() => fileInputRef.current?.click()}
          >
            {t("attachments.pick")}
          </button>
        )}
      </header>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={onPick}
        data-testid="attachment-file-input"
      />

      {canEdit && (
        <div
          role="region"
          aria-label={t("attachments.dropzone")}
          className={`rounded border-2 border-dashed p-6 text-center text-sm ${
            dragOver ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-slate-50"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          data-testid="attachment-dropzone"
        >
          {t("attachments.dropHint")}
        </div>
      )}

      {uploading && (
        <div className="rounded border border-slate-200 bg-white p-3 text-sm">
          <div className="flex justify-between">
            <span>{uploading.filename}</span>
            <span>
              {uploading.fraction === null
                ? t("attachments.uploading")
                : `${Math.round(uploading.fraction * 100)} %`}
            </span>
          </div>
          <progress
            className="mt-1 w-full"
            value={uploading.fraction ?? undefined}
            max={1}
            data-testid="attachment-upload-progress"
          />
        </div>
      )}

      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}

      {items === null && <p className="text-sm text-slate-500">{t("common.loading")}</p>}

      {items !== null && items.length === 0 && (
        <p className="text-sm text-slate-500">{t("attachments.empty")}</p>
      )}

      {items !== null && items.length > 0 && (
        <ul className="divide-y rounded border border-slate-200 bg-white">
          {items.map((a) => {
            const canDeleteThis = canEdit || a.uploaded_by === user?.id;
            return (
              <li key={a.id} className="flex items-center justify-between px-3 py-2 text-sm">
                <div className="min-w-0 flex-1">
                  <a
                    href={downloadUrl(a.id)}
                    className="block truncate text-blue-700 hover:underline"
                    download={a.filename}
                  >
                    {a.filename}
                  </a>
                  <p className="text-xs text-slate-500">
                    {formatBytes(a.size_bytes)}
                    {" — "}
                    {new Date(a.created_at).toLocaleDateString("de-CH")}
                  </p>
                </div>
                {canDeleteThis && (
                  <>
                    {confirmId === a.id ? (
                      <span className="ml-3 flex items-center gap-2">
                        <span className="text-xs text-slate-700">
                          {t("attachments.confirmDelete")}
                        </span>
                        <button
                          type="button"
                          className="rounded bg-red-600 px-2 py-0.5 text-xs text-white"
                          onClick={() => void onDelete(a.id)}
                          data-testid={`attachment-delete-confirm-${a.id}`}
                        >
                          {t("attachments.delete")}
                        </button>
                        <button
                          type="button"
                          className="rounded border border-slate-300 px-2 py-0.5 text-xs"
                          onClick={() => setConfirmId(null)}
                        >
                          {t("attachments.cancel")}
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="ml-3 rounded border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-100"
                        onClick={() => setConfirmId(a.id)}
                        aria-label={t("attachments.delete")}
                        data-testid={`attachment-delete-${a.id}`}
                      >
                        {t("attachments.delete")}
                      </button>
                    )}
                  </>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
