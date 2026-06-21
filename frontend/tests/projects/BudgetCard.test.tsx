import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n/i18n";
import { BudgetCard } from "@/features/projects/BudgetCard";

const baseProject = {
  id: "p1",
  object_id: "o1",
  name: "Test",
  description: null,
  status: "idea" as const,
  planned_year: null,
  rough_estimate_chf: null as string | number | null,
  archived_at: null,
  created_by: null,
  created_at: "",
  updated_at: "",
};

function withProviders(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>{ui}</I18nextProvider>
    </QueryClientProvider>
  );
}

describe("BudgetCard", () => {
  it("shows empty state when rough_estimate_chf is null", () => {
    render(
      withProviders(
        <BudgetCard project={baseProject} plannedTotal={0} onEstimateSaved={vi.fn()} />,
      ),
    );
    expect(screen.getByText(/Grobschätzung hinzufügen/i)).toBeInTheDocument();
  });

  it("shows planned total and difference (over)", () => {
    render(
      withProviders(
        <BudgetCard
          project={{ ...baseProject, rough_estimate_chf: "80000" }}
          plannedTotal={83200}
          onEstimateSaved={vi.fn()}
        />,
      ),
    );
    expect(screen.getByText(/80['’ ]?000/)).toBeInTheDocument();
    expect(screen.getByText(/83['’ ]?200/)).toBeInTheDocument();
    const diffNode = screen.getByTestId("budget-diff");
    expect(diffNode.textContent).toMatch(/3['’ ]?200/);
    expect(diffNode.className).toMatch(/negative/);
  });

  it("opens inline editor on edit click", () => {
    render(
      withProviders(
        <BudgetCard
          project={{ ...baseProject, rough_estimate_chf: "80000" }}
          plannedTotal={0}
          onEstimateSaved={vi.fn()}
        />,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: /Bearbeiten/i }));
    expect(screen.getByRole("spinbutton")).toBeInTheDocument();
  });
});
