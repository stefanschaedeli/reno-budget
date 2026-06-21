/**
 * Audit-log viewer (Phase 7).
 *
 * Two modes:
 *  - per-object view at /objekte/:id/audit (owner-only on the object)
 *  - global view at /admin/audit (superuser-only)
 *
 * The component pages backwards through the keyset feed using the
 * `next_before` cursor returned by the API. The "Weitere laden" button
 * fetches the next page and appends it to the list.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { ApiError } from "@/api/client";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { listGlobalAudit, listObjectAudit } from "./api";
import type { AuditEvent } from "./types";

type Mode = "object" | "global";

interface InnerProps {
  mode: Mode;
  objectId?: string;
}

export function ObjectAuditPage(): JSX.Element {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  if (!id)
    return (
      <PageContainer width="default">
        <p className="text-negative">{t("common.error")}</p>
      </PageContainer>
    );
  return <AuditViewer mode="object" objectId={id} />;
}

export function GlobalAuditPage(): JSX.Element {
  return <AuditViewer mode="global" />;
}

function AuditViewer({ mode, objectId }: InnerProps): JSX.Element {
  const { t } = useTranslation();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [nextBefore, setNextBefore] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = async (before: string | null): Promise<void> => {
    try {
      const page =
        mode === "object" && objectId
          ? await listObjectAudit(objectId, { before, limit: 50 })
          : await listGlobalAudit({ before, limit: 50 });
      setEvents((prev) => (before ? [...prev, ...page.items] : page.items));
      setNextBefore(page.next_before);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setError(t("audit.forbidden"));
      } else {
        setError(t("audit.loadFailed"));
      }
    }
  };

  useEffect(() => {
    setLoading(true);
    setError(null);
    void fetchPage(null).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, objectId]);

  const handleMore = async (): Promise<void> => {
    if (!nextBefore || loadingMore) return;
    setLoadingMore(true);
    await fetchPage(nextBefore);
    setLoadingMore(false);
  };

  const title = mode === "global" ? t("audit.globalTitle") : t("audit.title");

  if (loading) {
    return (
      <PageContainer width="default">
        <p className="text-ink-muted">{t("common.loading")}</p>
      </PageContainer>
    );
  }
  if (error) {
    return (
      <PageContainer width="default">
        <PageHeader title={title} />
        <p className="rounded border border-negative bg-negative-soft p-3 text-negative">
          {error}
        </p>
      </PageContainer>
    );
  }

  return (
    <PageContainer width="default">
      <PageHeader title={title} subtitle={t("audit.subtitle")} />

      {events.length === 0 ? (
        <p className="text-ink-muted">{t("audit.empty")}</p>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-rule text-left">
              <th className="py-2 pr-3">{t("audit.columns.time")}</th>
              <th className="py-2 pr-3">{t("audit.columns.actor")}</th>
              <th className="py-2 pr-3">{t("audit.columns.action")}</th>
              <th className="py-2 pr-3">{t("audit.columns.summary")}</th>
            </tr>
          </thead>
          <tbody>
            {events.map((ev) => (
              <AuditRow key={ev.id} event={ev} />
            ))}
          </tbody>
        </table>
      )}

      {nextBefore ? (
        <div className="mt-4">
          <button
            type="button"
            className="rounded border border-rule px-3 py-1.5 hover:bg-paper-sunk disabled:opacity-50"
            onClick={() => void handleMore()}
            disabled={loadingMore}
          >
            {loadingMore ? t("common.loading") : t("audit.loadMore")}
          </button>
        </div>
      ) : null}
    </PageContainer>
  );
}

function AuditRow({ event }: { event: AuditEvent }): JSX.Element {
  const { t, i18n } = useTranslation();
  const time = new Date(event.created_at).toLocaleString(i18n.language || "de-CH", {
    dateStyle: "short",
    timeStyle: "short",
  });
  // Look up a German label for the action, falling back to the raw verb.
  const actionLabel = t(`audit.actions.${event.action}`, {
    defaultValue: event.action,
  });
  return (
    <tr className="border-b border-rule align-top">
      <td className="py-2 pr-3 font-mono text-xs text-ink-muted">{time}</td>
      <td className="py-2 pr-3">{event.actor_email}</td>
      <td className="py-2 pr-3">{actionLabel}</td>
      <td className="py-2 pr-3">{event.summary}</td>
    </tr>
  );
}
