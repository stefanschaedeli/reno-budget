import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BkpGroupBreakdown } from "@/features/budget/BkpGroupBreakdown";
import { UnitBreakdown } from "@/features/budget/UnitBreakdown";
import { StatusPriorityBreakdown } from "@/features/budget/StatusPriorityBreakdown";
import { get, mockFetchByRoute, renderWithProviders } from "./helpers";

const OBJECT_ID = "00000000-0000-0000-0000-000000000001";

describe("BkpGroupBreakdown", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("aggregates rows by group and renders amounts", async () => {
    mockFetchByRoute([
      {
        match: get(`/objects/${OBJECT_ID}/budget/bkp-groups`),
        respond: () => ({
          body: {
            rows: [
              { group: "C", label: "Konstruktion Gebäude", planned_chf: "120000", actual_chf: "30000" },
              { group: "D", label: "Technik", planned_chf: "60000", actual_chf: "0" },
            ],
          },
        }),
      },
    ]);
    renderWithProviders(<BkpGroupBreakdown objectId={OBJECT_ID} year={null} />);
    await waitFor(() => {
      expect(screen.getByTestId("bkp-row-C")).toBeInTheDocument();
    });
    expect(screen.getByTestId("bkp-row-D")).toBeInTheDocument();
    expect(screen.getByText(/Konstruktion Gebäude/)).toBeInTheDocument();
  });

  it("renders empty state when no rows", async () => {
    mockFetchByRoute([
      {
        match: get(`/objects/${OBJECT_ID}/budget/bkp-groups`),
        respond: () => ({ body: { rows: [] } }),
      },
    ]);
    renderWithProviders(<BkpGroupBreakdown objectId={OBJECT_ID} year={null} />);
    await waitFor(() =>
      expect(screen.getByText("Keine Daten.")).toBeInTheDocument(),
    );
  });
});

describe("UnitBreakdown", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders one row per unit with pro-rated planned and actual", async () => {
    mockFetchByRoute([
      {
        match: get(`/objects/${OBJECT_ID}/budget/units`),
        respond: () => ({
          body: {
            rows: [
              {
                unit_id: "11111111-1111-1111-1111-111111111111",
                label: "EG",
                planned_chf: "40000",
                actual_chf: "5000",
              },
              {
                unit_id: "22222222-2222-2222-2222-222222222222",
                label: "OG",
                planned_chf: "60000",
                actual_chf: "10000",
              },
            ],
          },
        }),
      },
    ]);
    renderWithProviders(<UnitBreakdown objectId={OBJECT_ID} />);
    await waitFor(() =>
      expect(
        screen.getByTestId("unit-row-11111111-1111-1111-1111-111111111111"),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("EG")).toBeInTheDocument();
    expect(screen.getByText("OG")).toBeInTheDocument();
  });
});

describe("StatusPriorityBreakdown", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders the status x priority grid cells", async () => {
    mockFetchByRoute([
      {
        match: get(`/objects/${OBJECT_ID}/budget/status-priority`),
        respond: () => ({
          body: {
            rows: [
              { status: "planned", priority: "high", planned_chf: "50000", count: 2 },
              { status: "idea", priority: "low", planned_chf: "5000", count: 1 },
            ],
          },
        }),
      },
    ]);
    renderWithProviders(<StatusPriorityBreakdown objectId={OBJECT_ID} />);
    await waitFor(() =>
      expect(screen.getByTestId("sp-planned-high")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("sp-idea-low")).toBeInTheDocument();
    expect(screen.getByTestId("sp-completed-urgent")).toBeInTheDocument();
  });
});
