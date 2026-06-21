import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReservePanel } from "@/features/budget/ReservePanel";
import {
  get,
  mockFetchByRoute,
  patch,
  renderWithProviders,
} from "./helpers";

const OBJECT_ID = "00000000-0000-0000-0000-000000000001";

const ownerPlan = {
  object_id: OBJECT_ID,
  inflation_rate_percent: "1.5",
  initial_reserve_chf: "20000",
  contribution_mode: "yearly",
  horizon_years: 30,
  total_planned_inflated_chf: "300000",
  required_total_chf: "280000",
  required_per_year_chf: "9333.33",
  required_per_month_chf: "777.78",
  required_lump_sums: [],
  scope_pro_rated: false,
};

const lumpSumPlan = {
  ...ownerPlan,
  contribution_mode: "lump_sum",
  required_lump_sums: [
    { year: 2027, amount_chf: "10000" },
    { year: 2030, amount_chf: "25000" },
  ],
};

describe("ReservePanel", () => {
  afterEach(() => vi.unstubAllGlobals());

  describe("editable form", () => {
    beforeEach(() => {
      mockFetchByRoute([
        {
          match: get(`/objects/${OBJECT_ID}/budget/reserve`),
          respond: () => ({ body: ownerPlan }),
        },
        {
          match: patch(`/objects/${OBJECT_ID}`),
          respond: () => ({ body: { ...ownerPlan, contribution_mode: "monthly" } }),
        },
      ]);
    });

    it("renders editable inputs for mode, inflation rate, initial reserve", async () => {
      renderWithProviders(<ReservePanel objectId={OBJECT_ID} />);
      await waitFor(() => {
        expect(
          screen.getByText("Beitragsmodus"),
        ).toBeInTheDocument();
      });
      expect(screen.getByRole("button", { name: /Speichern/ })).toBeInTheDocument();
      expect(screen.getByLabelText(/Inflationsrate/)).toHaveValue(1.5);
    });

    it("submits a PATCH on save", async () => {
      const fetchMock = vi.mocked(globalThis.fetch);
      renderWithProviders(<ReservePanel objectId={OBJECT_ID} />);
      await waitFor(() =>
        expect(screen.getByLabelText(/Inflationsrate/)).toBeInTheDocument(),
      );
      fireEvent.click(screen.getByRole("button", { name: /Speichern/ }));
      await waitFor(() => {
        const patchCall = fetchMock.mock.calls.find(
          (c) => c[1]?.method === "PATCH",
        );
        expect(patchCall).toBeTruthy();
      });
    });
  });

  describe("formula label per mode", () => {
    it("uses 'CHF pro Jahr' for yearly mode", async () => {
      mockFetchByRoute([
        {
          match: get(`/objects/${OBJECT_ID}/budget/reserve`),
          respond: () => ({ body: ownerPlan }),
        },
      ]);
      renderWithProviders(<ReservePanel objectId={OBJECT_ID} />);
      await waitFor(() =>
        expect(screen.getByText(/CHF pro Jahr/)).toBeInTheDocument(),
      );
    });

    it("renders the lump-sum schedule table when mode is lump_sum", async () => {
      mockFetchByRoute([
        {
          match: get(`/objects/${OBJECT_ID}/budget/reserve`),
          respond: () => ({ body: lumpSumPlan }),
        },
      ]);
      renderWithProviders(<ReservePanel objectId={OBJECT_ID} />);
      await waitFor(() =>
        expect(screen.getByTestId("lump-sum-schedule")).toBeInTheDocument(),
      );
      expect(screen.getByText("2027")).toBeInTheDocument();
      expect(screen.getByText("2030")).toBeInTheDocument();
      expect(screen.getByText(/Einzahlungen nach Jahr/)).toBeInTheDocument();
    });
  });
});
