import { useEffect, useId, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

interface DrawerProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function Drawer({ title, onClose, children }: DrawerProps): JSX.Element {
  const { t } = useTranslation();
  const titleId = useId();
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  useEffect(() => {
    closeButtonRef.current?.focus();
  }, []);

  return (
    <div className="fixed inset-0 z-40 flex">
      <div
        className="flex-1 bg-ink/40"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="z-50 w-full max-w-xl overflow-y-auto bg-paper-raised p-6 shadow-xl"
      >
        <header className="mb-4 flex items-center justify-between">
          <h3 id={titleId} className="text-lg font-semibold">{title}</h3>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label={t("common.close")}
            className="text-ink-muted hover:text-ink"
          >
            ×
          </button>
        </header>
        {children}
      </aside>
    </div>
  );
}
