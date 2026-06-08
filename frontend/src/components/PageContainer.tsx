import type { ReactNode } from "react";

type Width = "narrow" | "default" | "wide";

const WIDTH_CLASS: Record<Width, string> = {
  narrow: "max-w-3xl",   // forms, detail pages
  default: "max-w-5xl",  // list pages
  wide: "max-w-6xl",     // dashboards (budget, renofond)
};

export function PageContainer({
  width = "default",
  children,
}: {
  width?: Width;
  children: ReactNode;
}): JSX.Element {
  return (
    <div className={`mx-auto ${WIDTH_CLASS[width]} p-6`}>{children}</div>
  );
}
