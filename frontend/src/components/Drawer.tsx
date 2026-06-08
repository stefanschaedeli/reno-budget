import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

interface DrawerProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function Drawer({ title, onClose, children }: DrawerProps): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-40 flex">
      <div
        className="flex-1 bg-slate-900/40"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside className="z-50 w-full max-w-xl overflow-y-auto bg-white p-6 shadow-xl">
        <header className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common.close")}
            className="text-slate-500 hover:text-slate-900"
          >
            ×
          </button>
        </header>
        {children}
      </aside>
    </div>
  );
}
