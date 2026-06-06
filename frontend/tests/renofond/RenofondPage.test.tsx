import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Route, Routes } from "react-router-dom";
import { RenofondPage } from "@/features/renofond/RenofondPage";
import {
  get,
  mockFetchByRoute,
  renderWithProviders,
} from "../budget/helpers";

const OBJECT_ID = "00000000-0000-0000-0000-000000000001";
const CURRENT_YEAR = new Date().getFullYear();

const baseProjection = {
  object_id: OBJECT_ID,
  current_year: CURRENT_YEAR,
  horizon_until_year: CURRENT_YEAR + 3,
  inflation_rate_percent: "0",
  initial_reserve_chf: "0",
  required_per_year_chf: "1000.00",
  rows: [
    {
      year: CURRENT_YEAR,
      required_contribution_chf: "0.00",
      actual_contribution_chf: "0.00",
      planned_spend_chf: "0.00",
      balance_chf: "0.00",
      cumulative_planned_chf: "0.00",
      is_underfunded: false,
    },
    {
      year: CURRENT_YEAR + 1,
      required_contribution_chf: "1000.00",
      actual_contribution_chf: "0.00",
      planned_spend_chf: "0.00",
      balance_chf: "1000.00",
      cumulative_planned_chf: "0.00",
      is_underfunded: false,
    },
    {
      year: CURRENT_YEAR + 2,
      required_contribution_chf: "1000.00",
      actual_contribution_chf: "0.00",
      planned_spend_chf: "5000.00",
      balance_chf: "-3000.00",
      cumulative_planned_chf: "5000.00",
      is_underfunded: true,
    },
    {
      year: CURRENT_YEAR + 3,
      required_contribution_chf: "1000.00",
      actual_contribution_chf: "0.00",
      planned_spend_chf: "0.00",
      balance_chf: "-2000.00",
      cumulative_planned_chf: "5000.00",
      is_underfunded: true,
    },
  ],
  underfunding_years: [
    { year: CURRENT_YEAR + 2, shortfall_chf: "3000.00" },
    { year: CURRENT_YEAR + 3, shortfall_chf: "2000.00" },
  ],
  scope_pro_rated: false,
};

const healthyProjection = {
  ...baseProjection,
  rows: baseProjection.rows.map((r) => ({
    ...r,
    balance_chf: "5000.00",
    is_underfunded: false,
  })),
  underfunding_years: [],
};

const ownerContributions = {
  my_role: "owner",
  items: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      object_id: OBJECT_ID,
      year: CURRENT_YEAR,
      amount_chf: "500.00",
      note: "Erste Einlage",
      created_at: "2026-01-01T00:00:00Z",
    },
  ],
};

const viewerContributions = { ...ownerContributions, my_role: "viewer" };
const emptyOwnerContributions = { my_role: "owner", items: [] };

function renderPage(): void {
  renderWithProviders(
    <Routes>
      <Route path="/objekte/:id/renofond" element={<RenofondPage />} />
    </Routes>,
    { initialRoute: `/objekte/${OBJECT_ID}/renofond` },
  );
}

describe("RenofondPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  describe("as OWNER with underfunding", () => {
    beforeEach(() => {
      mockFetchByRoute([
        {
          match: get(`/objects/${OBJECT_ID}/renofond/projection`),
          respond: () => ({ body: baseProjection }),
        },
        {
          match: get(`/objects/${OBJECT_ID}/renofond/contributions`),
          respond: () => ({ body: ownerContributions }),
        },
      ]);
    });

    it("renders the underfunding banner with the affected years", async () => {
      renderPage();
      await waitFor(() => {
        expect(screen.getByTestId("underfunding-banner")).toBeInTheDocument();
      });
      const banner = screen.getByTestId("underfunding-banner");
      expect(banner).toHaveTextContent(String(CURRENT_YEAR + 2));
      expect(banner).toHaveTextContent(String(CURRENT_YEAR + 3));
    });

    it("renders the projection chart with one group per planning year", async () => {
      renderPage();
      await waitFor(() => {
        expect(screen.getByTestId("projection-chart")).toBeInTheDocument();
      });
      // One <g> per row.
      for (const row of baseProjection.rows) {
        expect(
          screen.getByTestId(`projection-year-${row.year}`),
        ).toBeInTheDocument();
      }
    });

    it("renders the contributions table and the add form", async () => {
      renderPage();
      await waitFor(() => {
        expect(screen.getByTestId("contributions-table")).toBeInTheDocument();
      });
      expect(screen.getByText("Erste Einlage")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /Speichern/ }),
      ).toBeInTheDocument();
    });
  });

  describe("as OWNER without contributions yet", () => {
    beforeEach(() => {
      mockFetchByRoute([
        {
          match: get(`/objects/${OBJECT_ID}/renofond/projection`),
          respond: () => ({ body: healthyProjection }),
        },
        {
          match: get(`/objects/${OBJECT_ID}/renofond/contributions`),
          respond: () => ({ body: emptyOwnerContributions }),
        },
      ]);
    });

    it("shows the empty-state hint and no banner", async () => {
      renderPage();
      await waitFor(() => {
        expect(
          screen.getByTestId("contributions-empty"),
        ).toBeInTheDocument();
      });
      expect(
        screen.queryByTestId("underfunding-banner"),
      ).not.toBeInTheDocument();
    });

    it("submits a POST when the form is filled and Speichern is clicked", async () => {
      // Re-stub BEFORE rendering so we have a POST handler too, and capture
      // the mock afterwards.
      mockFetchByRoute([
        {
          match: get(`/objects/${OBJECT_ID}/renofond/projection`),
          respond: () => ({ body: healthyProjection }),
        },
        {
          match: get(`/objects/${OBJECT_ID}/renofond/contributions`),
          respond: () => ({ body: emptyOwnerContributions }),
        },
        {
          match: (url, init) =>
            init.method === "POST" &&
            url.includes(`/objects/${OBJECT_ID}/renofond/contributions`),
          respond: () => ({
            status: 201,
            body: {
              id: "22222222-2222-2222-2222-222222222222",
              object_id: OBJECT_ID,
              year: CURRENT_YEAR,
              amount_chf: "750.00",
              note: null,
              created_at: "2026-06-06T12:00:00Z",
            },
          }),
        },
      ]);
      const fetchMock = vi.mocked(globalThis.fetch);
      renderPage();
      await waitFor(() =>
        expect(screen.getByTestId("contributions-empty")).toBeInTheDocument(),
      );
      const inputs = screen.getAllByRole("textbox");
      // The amount input is the first text input (note is second).
      fireEvent.change(inputs[0]!, { target: { value: "750.00" } });
      fireEvent.click(screen.getByRole("button", { name: /Speichern/ }));
      await waitFor(() => {
        const postCall = fetchMock.mock.calls.find(
          (c) => c[1]?.method === "POST",
        );
        expect(postCall).toBeTruthy();
      });
    });
  });

  describe("as VIEWER", () => {
    beforeEach(() => {
      mockFetchByRoute([
        {
          match: get(`/objects/${OBJECT_ID}/renofond/projection`),
          respond: () => ({ body: healthyProjection }),
        },
        {
          match: get(`/objects/${OBJECT_ID}/renofond/contributions`),
          respond: () => ({ body: viewerContributions }),
        },
      ]);
    });

    it("renders the read-only hint and no add form", async () => {
      renderPage();
      await waitFor(() => {
        expect(
          screen.getByText(
            /Nur Eigentümer können Einzahlungen erfassen oder löschen/,
          ),
        ).toBeInTheDocument();
      });
      expect(
        screen.queryByRole("button", { name: /Speichern/ }),
      ).not.toBeInTheDocument();
    });
  });
});
