/**
 * Phase 11A: the cost-items list renders tag chips per row using a single
 * tag catalogue (passed by the page) + each item's batched ``tag_ids``.
 * Verifies the chips appear for tagged rows and not for untagged rows.
 */
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import "@/i18n/i18n";

import { CostItemList } from "@/features/costs/CostItemList";
import type { CostItem } from "@/features/costs/types";
import type { Tag } from "@/features/tags/types";

const OBJ_ID = "11111111-1111-1111-1111-111111111111";
const UNIT_ID = "22222222-2222-2222-2222-222222222222";
const TAG_A_ID = "33333333-3333-3333-3333-333333333333";
const TAG_B_ID = "44444444-4444-4444-4444-444444444444";

const tagA: Tag = {
  id: TAG_A_ID,
  object_id: OBJ_ID,
  key: "raum",
  value: "kueche",
  color: null,
  created_at: "2026-01-01T00:00:00Z",
};
const tagB: Tag = {
  id: TAG_B_ID,
  object_id: OBJ_ID,
  key: "phase",
  value: "1",
  color: null,
  created_at: "2026-01-01T00:00:00Z",
};

function mkItem(
  overrides: Partial<CostItem> & Pick<CostItem, "id" | "title">,
): CostItem {
  return {
    object_id: OBJ_ID,
    bkp_code: "D01",
    project_id: null,
    npk_code: null,
    description: null,
    status: "planned",
    priority: "med",
    planned_year: 2026,
    planned_amount_chf: "100.00",
    actual_amount_chf: null,
    actual_date: null,
    lifespan_years: null,
    warranty_until: null,
    scope: "shared",
    created_by: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    allocations: [{ unit_id: UNIT_ID, share_permille: 1000 }],
    bkp_allocations: [],
    tag_ids: null,
    ...overrides,
  };
}

describe("CostItemList tag chips", () => {
  it("renders a TagChip per tag_id resolved against the tag catalogue", () => {
    const items = [
      mkItem({
        id: "a1111111-1111-1111-1111-111111111111",
        title: "Mit Tags",
        tag_ids: [TAG_A_ID, TAG_B_ID],
      }),
      mkItem({
        id: "b1111111-1111-1111-1111-111111111111",
        title: "Ohne Tags",
        tag_ids: [],
      }),
    ];
    render(
      <CostItemList items={items} tags={[tagA, tagB]} onRowClick={() => {}} />,
    );

    // Tag chips for "Mit Tags" row.
    expect(screen.getByTestId(`tag-chip-${TAG_A_ID}`)).toBeInTheDocument();
    expect(screen.getByTestId(`tag-chip-${TAG_B_ID}`)).toBeInTheDocument();
    // Both titles render.
    expect(screen.getByText("Mit Tags")).toBeInTheDocument();
    expect(screen.getByText("Ohne Tags")).toBeInTheDocument();
  });

  it("renders no chips when tag_ids is null (include_tag_ids not requested)", () => {
    const items = [
      mkItem({
        id: "a1111111-1111-1111-1111-111111111111",
        title: "Egal",
        tag_ids: null,
      }),
    ];
    render(
      <CostItemList items={items} tags={[tagA, tagB]} onRowClick={() => {}} />,
    );
    expect(screen.queryByTestId(`tag-chip-${TAG_A_ID}`)).not.toBeInTheDocument();
    expect(screen.queryByTestId(`tag-chip-${TAG_B_ID}`)).not.toBeInTheDocument();
  });

  it("silently skips tag_ids that aren't in the catalogue", () => {
    const items = [
      mkItem({
        id: "a1111111-1111-1111-1111-111111111111",
        title: "Stale",
        tag_ids: ["99999999-9999-9999-9999-999999999999"],
      }),
    ];
    render(
      <CostItemList items={items} tags={[tagA, tagB]} onRowClick={() => {}} />,
    );
    expect(screen.getByText("Stale")).toBeInTheDocument();
    // No chip is rendered because the tag id is unknown.
    expect(screen.queryByTestId(/tag-chip-/)).not.toBeInTheDocument();
  });
});
