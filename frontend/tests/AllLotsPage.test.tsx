import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AllLotsPage } from "@/features/lots/AllLotsPage";
import { get, mockFetchByRoute, renderWithProviders } from "./budget/helpers";

const LOT_ROW = {
  id: "22222222-2222-2222-2222-222222222222",
  object_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  object_name: "Haus A",
  name: "Los 1",
  description: null,
  status: "draft",
  tender_deadline: null,
  awarded_quote_id: null,
  archived_at: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  cost_item_count: 0,
  cost_item_ids: [],
};

describe("AllLotsPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders rows with name and parent object", async () => {
    mockFetchByRoute([
      {
        match: get("/lots"),
        respond: () => ({ body: [LOT_ROW] }),
      },
    ]);
    renderWithProviders(<AllLotsPage />);
    await waitFor(() =>
      expect(screen.getByText("Los 1")).toBeInTheDocument(),
    );
    expect(screen.getByText("Haus A")).toBeInTheDocument();
  });

  it("renders empty state", async () => {
    mockFetchByRoute([
      {
        match: get("/lots"),
        respond: () => ({ body: [] }),
      },
    ]);
    renderWithProviders(<AllLotsPage />);
    await waitFor(() =>
      expect(
        screen.getByText("Noch keine Lose erfasst."),
      ).toBeInTheDocument(),
    );
  });
});
