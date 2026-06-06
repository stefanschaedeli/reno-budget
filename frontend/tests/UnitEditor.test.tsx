import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { UnitEditor } from "@/features/objects/UnitEditor";
import "@/i18n/i18n";

describe("UnitEditor", () => {
  it("shows balanced ‰ sum in green", () => {
    render(
      <UnitEditor
        units={[
          { label: "A", wertquote_permille: 500, area_m2: null },
          { label: "B", wertquote_permille: 500, area_m2: null },
        ]}
        onChange={() => {}}
      />,
    );
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(/1000‰/);
    expect(status.className).toMatch(/text-green-700/);
  });

  it("shows hint when sum is off", () => {
    render(
      <UnitEditor
        units={[
          { label: "A", wertquote_permille: 400, area_m2: null },
          { label: "B", wertquote_permille: 400, area_m2: null },
        ]}
        onChange={() => {}}
      />,
    );
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent(/800‰/);
    expect(status).toHaveTextContent(/1000/);
    expect(status.className).toMatch(/text-red-700/);
  });

  it("emits updates when a Wertquote input changes", () => {
    const onChange = vi.fn();
    render(
      <UnitEditor
        units={[
          { label: "A", wertquote_permille: 500, area_m2: null },
          { label: "B", wertquote_permille: 500, area_m2: null },
        ]}
        onChange={onChange}
      />,
    );
    const wqInputs = screen.getAllByLabelText(/Wertquote/);
    fireEvent.change(wqInputs[0]!, { target: { value: "600" } });
    expect(onChange).toHaveBeenCalledWith([
      { label: "A", wertquote_permille: 600, area_m2: null },
      { label: "B", wertquote_permille: 500, area_m2: null },
    ]);
  });
});
