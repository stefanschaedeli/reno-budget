import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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

describe("CostItemFilters", () => {
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
      <MemoryRouter initialEntries={["/objekte/x/kosten"]}>
        <CostItemFilters units={units} onChange={onChange} />
        <LocationProbe onLocation={(s) => (lastSearch = s)} />
      </MemoryRouter>,
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

  it("round-trips a year value via the URL", () => {
    let lastSearch = "";
    render(
      <MemoryRouter initialEntries={["/objekte/x/kosten"]}>
        <CostItemFilters units={units} onChange={() => {}} />
        <LocationProbe onLocation={(s) => (lastSearch = s)} />
      </MemoryRouter>,
    );
    const yearInput = screen.getByLabelText(/Geplantes Jahr/);
    fireEvent.change(yearInput, { target: { value: "2030" } });
    expect(lastSearch).toContain("year=2030");
  });
});
