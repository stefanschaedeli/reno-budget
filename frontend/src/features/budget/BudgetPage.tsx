import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { ReservePanel } from "./ReservePanel";
import { TimelineChart } from "./TimelineChart";

export function BudgetPage(): JSX.Element {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();

  if (!id)
    return (
      <PageContainer width="wide">
        <p className="text-negative">{t("common.error")}</p>
      </PageContainer>
    );

  return (
    <PageContainer width="wide">
      <PageHeader
        title={t("budget.title")}
        actions={
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="self-center text-ink-muted">{t("export.label")}:</span>
            <a
              href={`/api/v1/objects/${id}/export/xlsx`}
              className="rounded border border-rule bg-paper-raised px-3 py-1 hover:bg-paper-sunk"
            >
              {t("export.xlsx")}
            </a>
            <a
              href={`/api/v1/objects/${id}/export/pdf`}
              className="rounded border border-rule bg-paper-raised px-3 py-1 hover:bg-paper-sunk"
            >
              {t("export.pdf")}
            </a>
            <a
              href={`/api/v1/objects/${id}/export/npk`}
              className="rounded border border-rule bg-paper-raised px-3 py-1 hover:bg-paper-sunk"
            >
              {t("export.npk")}
            </a>
          </div>
        }
      />

      <div className="space-y-6">
        <ReservePanel objectId={id} />

        <div className="rounded border border-rule bg-paper-raised p-4">
          <TimelineChart objectId={id} />
        </div>
      </div>
    </PageContainer>
  );
}
