import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TimelineChart } from "@/features/budget/TimelineChart";
import {
  get,
  mockFetchByRoute,
  renderWithProviders,
} from "./helpers";

const OBJECT_ID = "00000000-0000-0000-0000-000000000001";

const baseTimeline = {
  object_id: OBJECT_ID,
  my_role: "owner",
  is_scoped: false,
  rows: [
    {
      year: 2026,
      planned_chf: "10000",
      planned_inflated_chf: "10500",
      actual_chf: "5000",
    },
    {
      year: 2027,
      planned_chf: "20000",
      planned_inflated_chf: "21000",
      actual_chf: "0",
    },
  ],
};

const drill = {
  year: 2026,
  items: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      title: "Fenster ersetzen",
      bkp_code: "C2.04",
      status: "planned",
      priority: "med",
      planned_amount_chf: "10000",
      actual_amount_chf: null,
    },
  ],
};

describe("TimelineChart", () => {
  beforeEach(() => {
    mockFetchByRoute([
      {
        match: get("/budget/timeline?inflated=1"),
        respond: () => ({ body: baseTimeline }),
      },
      {
        match: get("/budget/timeline?inflated=0"),
        respond: () => ({ body: baseTimeline }),
      },
      {
        match: get(`/budget/timeline/2026`),
        respond: () => ({ body: drill }),
      },
    ]);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("renders bars with planned (inflated) and actual values per year", async () => {
    renderWithProviders(<TimelineChart objectId={OBJECT_ID} />);
    const row2026 = await screen.findByTestId("timeline-year-2026");
    expect(row2026.getAttribute("data-planned")).toBe("10500");
    expect(row2026.getAttribute("data-actual")).toBe("5000");
    const row2027 = screen.getByTestId("timeline-year-2027");
    expect(row2027.getAttribute("data-planned")).toBe("21000");
  });

  it("switches planned series when nominal toggle is selected", async () => {
    renderWithProviders(<TimelineChart objectId={OBJECT_ID} />);
    await screen.findByTestId("timeline-year-2026");
    fireEvent.click(screen.getByLabelText(/Nominal/));
    await waitFor(() => {
      expect(
        screen.getByTestId("timeline-year-2026").getAttribute("data-planned"),
      ).toBe("10000");
    });
  });

  it("drills down into a year on click", async () => {
    renderWithProviders(<TimelineChart objectId={OBJECT_ID} />);
    const row2026 = await screen.findByTestId("timeline-year-2026");
    fireEvent.click(row2026);
    await waitFor(() => {
      expect(screen.getByText("Fenster ersetzen")).toBeInTheDocument();
    });
  });

  it("shows a German friendly message on 403", async () => {
    vi.unstubAllGlobals();
    mockFetchByRoute([
      {
        match: get("/budget/timeline"),
        respond: () => ({ status: 403, body: { detail: "forbidden" } }),
      },
    ]);
    renderWithProviders(<TimelineChart objectId={OBJECT_ID} />);
    await waitFor(() => {
      expect(
        screen.getByText(/Keine Berechtigung/),
      ).toBeInTheDocument();
    });
  });
});
