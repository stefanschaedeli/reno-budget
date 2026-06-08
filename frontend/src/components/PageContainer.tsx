import type { ReactNode } from "react";

type Width = "narrow" | "default" | "wide";

function widthClass(width: Width): string {
  switch (width) {
    case "narrow":
      return "max-w-3xl"; // forms, detail pages
    case "wide":
      return "max-w-6xl"; // dashboards (budget, renofond)
    default:
      return "max-w-5xl"; // list pages
  }
}

export function PageContainer({
  width = "default",
  children,
}: {
  width?: Width;
  children: ReactNode;
}): JSX.Element {
  return (
    <div className={`mx-auto ${widthClass(width)} p-6`}>{children}</div>
  );
}
