import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FinancesPage } from "@/features/budget/FinancesPage";
import { get, mockFetchByRoute, renderWithProviders } from "./helpers";

const ROW_A = {
  object_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  name: "Haus Aarau",
  role: "owner",
  is_scoped: false,
  total_planned_inflated_chf: "300000",
  total_actual_chf: "10000",
  required_per_year_chf: "9000",
};
const ROW_B = {
  object_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  name: "Wohnung Zürich",
  role: "editor",
  is_scoped: true,
  total_planned_inflated_chf: "200000",
  total_actual_chf: "20000",
  required_per_year_chf: "15000",
};

describe("FinancesPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders rows sorted by required-per-year descending", async () => {
    mockFetchByRoute([
      {
        match: get("/finances"),
        respond: () => ({ body: { rows: [ROW_A, ROW_B] } }),
      },
    ]);
    renderWithProviders(<FinancesPage />);
    await waitFor(() =>
      expect(screen.getByText("Haus Aarau")).toBeInTheDocument(),
    );
    const rows = screen.getAllByRole("row");
    // first row is the header
    expect(within(rows[1]!).getByText("Wohnung Zürich")).toBeInTheDocument();
    expect(within(rows[2]!).getByText("Haus Aarau")).toBeInTheDocument();
  });

  it("shows scope badge for scoped rows only", async () => {
    mockFetchByRoute([
      {
        match: get("/finances"),
        respond: () => ({ body: { rows: [ROW_A, ROW_B] } }),
      },
    ]);
    renderWithProviders(<FinancesPage />);
    await waitFor(() =>
      expect(screen.getByText("Wohnung Zürich")).toBeInTheDocument(),
    );
    expect(
      screen.getByTestId(`scoped-badge-${ROW_B.object_id}`),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId(`scoped-badge-${ROW_A.object_id}`),
    ).not.toBeInTheDocument();
  });

  it("shows empty state when no objects", async () => {
    mockFetchByRoute([
      {
        match: get("/finances"),
        respond: () => ({ body: { rows: [] } }),
      },
    ]);
    renderWithProviders(<FinancesPage />);
    await waitFor(() =>
      expect(
        screen.getByText("Keine Objekte verfügbar."),
      ).toBeInTheDocument(),
    );
  });

  it("shows a generic German error message on failure", async () => {
    mockFetchByRoute([
      {
        match: get("/finances"),
        respond: () => ({ status: 500, body: { detail: "boom" } }),
      },
    ]);
    renderWithProviders(<FinancesPage />);
    await waitFor(() =>
      expect(
        screen.getByText("Budgetdaten konnten nicht geladen werden."),
      ).toBeInTheDocument(),
    );
  });
});
