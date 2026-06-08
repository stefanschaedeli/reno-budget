import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AllProjectsPage } from "@/features/projects/AllProjectsPage";
import { get, mockFetchByRoute, renderWithProviders } from "./budget/helpers";

const PROJECT_ROW = {
  id: "11111111-1111-1111-1111-111111111111",
  object_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  object_name: "Haus A",
  name: "Dach sanieren",
  description: null,
  status: "planned",
  planned_year: 2027,
  rough_estimate_chf: "75000.00",
  archived_at: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("AllProjectsPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders rows with name and parent object", async () => {
    mockFetchByRoute([
      {
        match: get("/projects"),
        respond: () => ({ body: [PROJECT_ROW] }),
      },
    ]);
    renderWithProviders(<AllProjectsPage />);
    await waitFor(() =>
      expect(screen.getByText("Dach sanieren")).toBeInTheDocument(),
    );
    expect(screen.getByText("Haus A")).toBeInTheDocument();
    expect(screen.getByText(/Grobschätzung/)).toBeInTheDocument();
  });

  it("renders empty state", async () => {
    mockFetchByRoute([
      {
        match: get("/projects"),
        respond: () => ({ body: [] }),
      },
    ]);
    renderWithProviders(<AllProjectsPage />);
    await waitFor(() =>
      expect(
        screen.getByText("Noch keine Projekte erfasst."),
      ).toBeInTheDocument(),
    );
  });
});
