import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";
import {
  CostItemFilters,
  parseFiltersFromParams,
} from "@/features/costs/CostItemFilters";
import type { Unit } from "@/features/objects/types";
import "@/i18n/i18n";

const units: Unit[] = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    object_id: "00000000-0000-0000-0000-000000000000",
    label: "EG",
    wertquote_permille: 400,
    area_m2: null,
  },
];

function LocationProbe({
  onLocation,
}: {
  onLocation: (search: string) => void;
}): null {
  const loc = useLocation();
  onLocation(loc.search);
  return null;
}

function withProviders(ui: React.ReactElement, route = "/objekte/x/kosten") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

const OBJ_ID = "00000000-0000-0000-0000-000000000000";

describe("CostItemFilters", () => {
  beforeEach(() => {
    // Mock empty tags + projects so the picker is happy.
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify([]), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
        ),
      ),
    );
  });
  afterEach(() => vi.unstubAllGlobals());
  it("parses status, priority, year, unit, bkp, q from URL", () => {
    const params = new URLSearchParams(
      "status=planned&status=in_progress&priority=high&year=2027&unit=u1&bkp=C&q=fenster",
    );
    const parsed = parseFiltersFromParams(params);
    expect(parsed.status).toEqual(["planned", "in_progress"]);
    expect(parsed.priority).toEqual(["high"]);
    expect(parsed.planned_year).toBe(2027);
    expect(parsed.unit_id).toBe("u1");
    expect(parsed.bkp_prefix).toBe("C");
    expect(parsed.q).toBe("fenster");
  });

  it("ignores unknown status / priority values", () => {
    const params = new URLSearchParams("status=bogus&priority=nope&year=abc");
    const parsed = parseFiltersFromParams(params);
    expect(parsed.status).toBeUndefined();
    expect(parsed.priority).toBeUndefined();
    expect(parsed.planned_year).toBeNull();
  });

  it("writes selected status back to URL search params", () => {
    let lastSearch = "";
    const onChange = vi.fn();
    render(
      withProviders(
        <>
          <CostItemFilters units={units} objectId={OBJ_ID} onChange={onChange} />
          <LocationProbe onLocation={(s) => (lastSearch = s)} />
        </>,
      ),
    );

    // initial onChange call with empty filters
    expect(onChange).toHaveBeenCalled();

    act(() => {
      fireEvent.click(screen.getByText("Geplant"));
    });

    expect(lastSearch).toContain("status=planned");
    // last invocation of onChange should reflect new state
    const calls = onChange.mock.calls as Array<[{ status?: string[] }]>;
    const lastCall = calls.at(-1);
    expect(lastCall?.[0]?.status).toEqual(["planned"]);
  });

  it("parses the lot filter from URL", () => {
    const params = new URLSearchParams("lot=aaaa1111-1111-1111-1111-111111111111");
    const parsed = parseFiltersFromParams(params);
    expect(parsed.lot_id).toBe("aaaa1111-1111-1111-1111-111111111111");
  });

  it("writes lot selection back to URL search params", async () => {
    const LOT_ID = "bbbb2222-2222-2222-2222-222222222222";
    // Override fetch so the lots endpoint returns one lot the user can select.
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
        const body = url.includes("/lots")
          ? [
              {
                id: LOT_ID,
                object_id: OBJ_ID,
                name: "L1",
                description: null,
                status: "draft",
                tender_deadline: null,
                awarded_quote_id: null,
                archived_at: null,
                created_by: null,
                created_at: "2026-01-01T00:00:00Z",
                updated_at: "2026-01-01T00:00:00Z",
                cost_item_count: 0,
                cost_item_ids: null,
              },
            ]
          : [];
        return Promise.resolve(
          new Response(JSON.stringify(body), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
        );
      }),
    );

    let lastSearch = "";
    render(
      withProviders(
        <>
          <CostItemFilters units={units} objectId={OBJ_ID} onChange={() => {}} />
          <LocationProbe onLocation={(s) => (lastSearch = s)} />
        </>,
      ),
    );
    // Wait for the lot option to appear in the DOM.
    const lotSelect = screen.getByLabelText(/^Los/);
    await waitFor(() => {
      expect(lotSelect.querySelector(`option[value="${LOT_ID}"]`)).not.toBeNull();
    });
    fireEvent.change(lotSelect, { target: { value: LOT_ID } });
    expect(lastSearch).toContain(`lot=${LOT_ID}`);
  });

  it("round-trips a year value via the URL", () => {
    let lastSearch = "";
    render(
      withProviders(
        <>
          <CostItemFilters units={units} objectId={OBJ_ID} onChange={() => {}} />
          <LocationProbe onLocation={(s) => (lastSearch = s)} />
        </>,
      ),
    );
    const yearInput = screen.getByLabelText(/Geplantes Jahr/);
    fireEvent.change(yearInput, { target: { value: "2030" } });
    expect(lastSearch).toContain("year=2030");
  });
});
