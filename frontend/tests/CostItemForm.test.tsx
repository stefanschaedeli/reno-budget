import "@testing-library/jest-dom/vitest";
import { describe, expect, it } from "vitest";
import { costItemInputSchema } from "@/features/costs/types";

/**
 * Validates the Zod contract that backs CostItemForm. Component-level
 * rendering is covered indirectly by the other suites; here we lock the
 * schema against the documented invariants (mirroring backend).
 */
describe("costItemInputSchema", () => {
  const validShared = {
    bkp_code: "C2",
    title: "Fenster ersetzen",
    status: "planned" as const,
    priority: "med" as const,
    planned_amount_chf: "12000.00",
    scope: "shared" as const,
    allocations: [
      { unit_id: "11111111-1111-1111-1111-111111111111", share_permille: 1000 },
    ],
  };

  it("accepts a minimal valid shared item", () => {
    const result = costItemInputSchema.safeParse(validShared);
    expect(result.success).toBe(true);
  });

  it("requires a title", () => {
    const result = costItemInputSchema.safeParse({
      ...validShared,
      title: "",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(
        result.error.issues.some((i) => i.path.includes("title")),
      ).toBe(true);
    }
  });

  it("requires a bkp_code", () => {
    const result = costItemInputSchema.safeParse({
      ...validShared,
      bkp_code: "",
    });
    expect(result.success).toBe(false);
  });

  it("requires at least one of planned/actual amount", () => {
    const result = costItemInputSchema.safeParse({
      ...validShared,
      planned_amount_chf: null,
      actual_amount_chf: null,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(
        result.error.issues.some((i) =>
          i.message.includes("Mindestens ein Betrag"),
        ),
      ).toBe(true);
    }
  });

  it("scope=unit requires non-empty allocations", () => {
    const result = costItemInputSchema.safeParse({
      ...validShared,
      scope: "unit",
      allocations: [],
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(
        result.error.issues.some((i) =>
          i.message.includes("Pro Einheit"),
        ),
      ).toBe(true);
    }
  });

  it("allocations must sum to 1000‰", () => {
    const result = costItemInputSchema.safeParse({
      ...validShared,
      allocations: [
        { unit_id: "11111111-1111-1111-1111-111111111111", share_permille: 400 },
        { unit_id: "22222222-2222-2222-2222-222222222222", share_permille: 400 },
      ],
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(
        result.error.issues.some((i) => i.message.includes("1000‰")),
      ).toBe(true);
    }
  });

  it("rejects malformed CHF amounts", () => {
    const result = costItemInputSchema.safeParse({
      ...validShared,
      planned_amount_chf: "abc",
    });
    expect(result.success).toBe(false);
  });
});
