import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AllocationEditor } from "@/features/costs/AllocationEditor";
import type { Unit } from "@/features/objects/types";
import type { CostItemAllocation } from "@/features/costs/types";
import "@/i18n/i18n";

const units: Unit[] = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    object_id: "00000000-0000-0000-0000-000000000000",
    label: "EG",
    wertquote_permille: 400,
    area_m2: 80,
  },
  {
    id: "22222222-2222-2222-2222-222222222222",
    object_id: "00000000-0000-0000-0000-000000000000",
    label: "1. OG",
    wertquote_permille: 600,
    area_m2: 100,
  },
];

const wertquoteAlloc: CostItemAllocation[] = [
  { unit_id: units[0]!.id, share_permille: 400 },
  { unit_id: units[1]!.id, share_permille: 600 },
];

describe("AllocationEditor", () => {
  it("shows balanced ‰ sum in green for SHARED defaults", () => {
    render(
      <AllocationEditor
        scope="shared"
        units={units}
        value={wertquoteAlloc}
        onChange={() => {}}
      />,
    );
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(/1000‰/);
    expect(status.className).toMatch(/text-positive/);
  });

  it("warns on sum != 1000‰", () => {
    render(
      <AllocationEditor
        scope="shared"
        units={units}
        value={[
          { unit_id: units[0]!.id, share_permille: 300 },
          { unit_id: units[1]!.id, share_permille: 600 },
        ]}
        onChange={() => {}}
      />,
    );
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(/900‰/);
    expect(status.className).toMatch(/text-negative/);
  });

  it("UNIT mode starts empty and surfaces hint", () => {
    render(
      <AllocationEditor
        scope="unit"
        units={units}
        value={[]}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText(/Noch keine Zuteilung/)).toBeInTheDocument();
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(/0‰/);
  });

  it("Standard zurücksetzen restores Wertquote distribution", () => {
    const onChange = vi.fn();
    render(
      <AllocationEditor
        scope="shared"
        units={units}
        value={[
          { unit_id: units[0]!.id, share_permille: 500 },
          { unit_id: units[1]!.id, share_permille: 500 },
        ]}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByText(/Standard \(Wertquote\)/));
    expect(onChange).toHaveBeenCalledWith([
      { unit_id: units[0]!.id, share_permille: 400 },
      { unit_id: units[1]!.id, share_permille: 600 },
    ]);
  });

  it("emits updated share when input changes", () => {
    const onChange = vi.fn();
    render(
      <AllocationEditor
        scope="shared"
        units={units}
        value={wertquoteAlloc}
        onChange={onChange}
      />,
    );
    const inputs = screen.getAllByLabelText(/Anteil ‰/);
    fireEvent.change(inputs[0]!, { target: { value: "350" } });
    expect(onChange).toHaveBeenCalledWith([
      { unit_id: units[0]!.id, share_permille: 350 },
      { unit_id: units[1]!.id, share_permille: 600 },
    ]);
  });
});
