import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BkpAllocationEditor } from "@/components/BkpAllocationEditor";
import type { BkpAllocationItem, BkpCode } from "@/features/costs/types";
import "@/i18n/i18n";

const codes: BkpCode[] = [
  {
    code: "C2.04",
    parent_code: "C2",
    level: 2,
    label_de: "Fenster",
    description: null,
    is_seed: true,
  },
  {
    code: "D5.02",
    parent_code: "D5",
    level: 2,
    label_de: "Sanitär",
    description: null,
    is_seed: true,
  },
];

describe("BkpAllocationEditor", () => {
  it("renders the empty state and an Add control", () => {
    render(
      <BkpAllocationEditor value={[]} onChange={() => {}} bkpCodes={codes} />,
    );
    expect(screen.getByText(/Noch keine Aufteilung/)).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("flags an unbalanced sum in red", () => {
    const value: BkpAllocationItem[] = [
      { bkp_code: "C2.04", share_permille: 400 },
      { bkp_code: "D5.02", share_permille: 500 },
    ];
    render(
      <BkpAllocationEditor
        value={value}
        onChange={() => {}}
        bkpCodes={codes}
      />,
    );
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(/900‰/);
    expect(status.className).toMatch(/text-red-700/);
  });

  it("renders a balanced sum in green", () => {
    const value: BkpAllocationItem[] = [
      { bkp_code: "C2.04", share_permille: 600 },
      { bkp_code: "D5.02", share_permille: 400 },
    ];
    render(
      <BkpAllocationEditor
        value={value}
        onChange={() => {}}
        bkpCodes={codes}
      />,
    );
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(/1000‰/);
    expect(status.className).toMatch(/text-green-700/);
  });

  it("calls onChange when adding a code from the dropdown", () => {
    const onChange = vi.fn();
    render(
      <BkpAllocationEditor value={[]} onChange={onChange} bkpCodes={codes} />,
    );
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "C2.04" },
    });
    expect(onChange).toHaveBeenCalledWith([
      { bkp_code: "C2.04", share_permille: 0 },
    ]);
  });

  it("removes a row via the Remove button", () => {
    const onChange = vi.fn();
    const value: BkpAllocationItem[] = [
      { bkp_code: "C2.04", share_permille: 1000 },
    ];
    render(
      <BkpAllocationEditor
        value={value}
        onChange={onChange}
        bkpCodes={codes}
      />,
    );
    fireEvent.click(screen.getByText(/Entfernen/));
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
