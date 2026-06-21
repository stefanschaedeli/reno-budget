import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import "@/i18n/i18n";
import { QuestionField, validateAnswer } from "@/features/ai/QuestionField";
import type { GeneratedQuestion } from "@/features/ai/types";

const numberQ: GeneratedQuestion = {
  key: "area_m2",
  label: "Dachfläche?",
  type: "number",
  unit: "m²",
  required: true,
  min: 1,
  max: 1000,
  options: null,
};

const selectQ: GeneratedQuestion = {
  key: "insulation",
  label: "Dämmung?",
  type: "select",
  required: true,
  options: ["Standard", "Hoch"],
};

describe("validateAnswer", () => {
  it("requires a value for required fields", () => {
    expect(validateAnswer(numberQ, null)).toBe("Pflichtfeld");
  });

  it("enforces the numeric minimum", () => {
    expect(validateAnswer(numberQ, 0)).toContain("Mindestens");
  });

  it("enforces the numeric maximum", () => {
    expect(validateAnswer(numberQ, 5000)).toContain("Höchstens");
  });

  it("accepts an in-range number", () => {
    expect(validateAnswer(numberQ, 120)).toBeNull();
  });
});

describe("QuestionField", () => {
  it("renders a number input with the unit in the label", () => {
    render(<QuestionField question={numberQ} value={null} onChange={vi.fn()} />);
    expect(screen.getByText(/Dachfläche\? \(m²\)/)).toBeInTheDocument();
    expect(screen.getByLabelText("Dachfläche?")).toHaveAttribute("type", "number");
  });

  it("emits a numeric value on change", () => {
    const onChange = vi.fn();
    render(<QuestionField question={numberQ} value={null} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Dachfläche?"), {
      target: { value: "120" },
    });
    expect(onChange).toHaveBeenCalledWith(120);
  });

  it("renders select options", () => {
    render(<QuestionField question={selectQ} value={null} onChange={vi.fn()} />);
    expect(screen.getByRole("option", { name: "Standard" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Hoch" })).toBeInTheDocument();
  });

  it("shows a validation error for an out-of-range number", () => {
    render(<QuestionField question={numberQ} value={5000} onChange={vi.fn()} />);
    expect(screen.getByText(/Höchstens/)).toBeInTheDocument();
  });
});
