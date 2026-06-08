import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { BkpGroupBreakdown } from "./BkpGroupBreakdown";
import { ReservePanel } from "./ReservePanel";
import { StatusPriorityBreakdown } from "./StatusPriorityBreakdown";
import { TimelineChart } from "./TimelineChart";
import { UnitBreakdown } from "./UnitBreakdown";

type Tab = "bkp" | "units" | "status";

export function BudgetPage(): JSX.Element {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<Tab>("bkp");

  if (!id)
    return (
      <PageContainer width="wide">
        <p className="text-red-700">{t("common.error")}</p>
      </PageContainer>
    );

  return (
    <PageContainer width="wide">
      <PageHeader
        title={t("budget.title")}
        actions={
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="self-center text-slate-500">{t("export.label")}:</span>
            <a
              href={`/api/v1/objects/${id}/export/xlsx`}
              className="rounded border border-slate-300 bg-white px-3 py-1 hover:bg-slate-50"
            >
              {t("export.xlsx")}
            </a>
            <a
              href={`/api/v1/objects/${id}/export/pdf`}
              className="rounded border border-slate-300 bg-white px-3 py-1 hover:bg-slate-50"
            >
              {t("export.pdf")}
            </a>
            <a
              href={`/api/v1/objects/${id}/export/npk`}
              className="rounded border border-slate-300 bg-white px-3 py-1 hover:bg-slate-50"
            >
              {t("export.npk")}
            </a>
          </div>
        }
      />

      <div className="space-y-6">
      <ReservePanel objectId={id} />

      <div className="rounded border border-slate-200 bg-white p-4">
        <TimelineChart objectId={id} />
      </div>

      <div className="rounded border border-slate-200 bg-white p-4">
        <div
          role="tablist"
          aria-label={t("budget.title")}
          className="mb-4 flex gap-2 border-b border-slate-200"
        >
          {(["bkp", "units", "status"] as const).map((k) => (
            <button
              key={k}
              role="tab"
              aria-selected={tab === k}
              onClick={() => setTab(k)}
              className={`px-3 py-2 text-sm ${
                tab === k
                  ? "border-b-2 border-slate-900 font-medium"
                  : "text-slate-500"
              }`}
            >
              {k === "bkp" && t("budget.bkpGroup.title")}
              {k === "units" && t("budget.unit.title")}
              {k === "status" && t("budget.statusPriority.title")}
            </button>
          ))}
        </div>
        {tab === "bkp" && <BkpGroupBreakdown objectId={id} year={null} />}
        {tab === "units" && <UnitBreakdown objectId={id} />}
        {tab === "status" && <StatusPriorityBreakdown objectId={id} />}
      </div>
      </div>
    </PageContainer>
  );
}
