import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
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

  if (!id) return <p className="p-6 text-red-700">{t("common.error")}</p>;

  return (
    <section className="mx-auto mt-8 max-w-6xl space-y-6 p-6">
      <header className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">{t("budget.title")}</h2>
        <nav className="flex gap-2 text-sm">
          <Link
            to={`/objekte/${id}`}
            className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100"
          >
            {t("objects.detail.tabUnits")}
          </Link>
          <Link
            to={`/objekte/${id}/kosten`}
            className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100"
          >
            {t("costs.title")}
          </Link>
          <Link
            to={`/objekte/${id}/renofond`}
            className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100"
          >
            {t("renofond.tab")}
          </Link>
        </nav>
      </header>

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
    </section>
  );
}
