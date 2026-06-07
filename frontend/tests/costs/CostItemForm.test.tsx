/**
 * Phase 11A fix: tags picked during cost-item *create* must be assigned to the
 * freshly-created item via assignTag(). The orchestration lives in the form's
 * parent (CostsPage); the form's contract is "pass the local tag selection up
 * via onSubmit(payload, pendingTags)". These tests verify both halves:
 *
 * 1. CostItemForm.onSubmit hands the picked tags to the parent.
 * 2. CostsPage.handleSubmit fans those out to assignTag() after create.
 */
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@/i18n/i18n";

// ---- Mocks --------------------------------------------------------------- //

const mockAssignTag = vi.fn();
const mockUnassignTag = vi.fn();

// Tag catalogue used by both the page-level useTags and the picker. Mutated
// by tests to simulate empty / non-empty fixtures.
const tagCatalogue: Array<{
  id: string;
  object_id: string;
  key: string;
  value: string;
  color: string | null;
  created_at: string;
}> = [];

vi.mock("@/features/tags/api", () => {
  return {
    useTags: () => ({ data: tagCatalogue, isLoading: false }),
    useTagsForTarget: () => ({ data: [], isLoading: false }),
    useAssignTag: () => ({ mutateAsync: vi.fn() }),
    useUnassignTag: () => ({ mutateAsync: vi.fn() }),
    useCreateTag: () => ({ mutateAsync: vi.fn(), isPending: false }),
    assignTag: (tagId: string, target: unknown): unknown =>
      mockAssignTag(tagId, target) as unknown,
    unassignTag: (tagId: string, target: unknown): unknown =>
      mockUnassignTag(tagId, target) as unknown,
    targetTagsKey: (t: string, id: string) => ["target-tags", t, id],
    tagsKey: (id: string) => ["tags", id],
  };
});

const mockCreateCostItem = vi.fn();
const mockUpdateCostItem = vi.fn();
const mockDeleteCostItem = vi.fn();

vi.mock("@/api/costs", () => {
  // Replace the hooks the page uses directly so internal sibling-imports
  // (e.g. useCreateCostItem -> createCostItem) don't escape the mock.
  return {
    useCostItems: () => ({
      data: [],
      isLoading: false,
      isError: false,
    }),
    useCreateCostItem: () => ({
      mutateAsync: (payload: unknown): unknown =>
        mockCreateCostItem(payload) as unknown,
      isPending: false,
    }),
    useUpdateCostItem: () => ({
      mutateAsync: (payload: unknown): unknown =>
        mockUpdateCostItem(payload) as unknown,
      isPending: false,
    }),
    useDeleteCostItem: () => ({
      mutateAsync: (id: string): unknown => mockDeleteCostItem(id) as unknown,
    }),
    useUpdateCostItemStatus: () => ({
      mutateAsync: () => Promise.resolve(),
    }),
  };
});

const mockGetObject = vi.fn();
vi.mock("@/features/objects/api", () => ({
  getObject: (...a: unknown[]): unknown => mockGetObject(...a) as unknown,
}));

vi.mock("@/api/bkp", () => ({
  useBkpCodes: () => ({ data: [], isLoading: false }),
  useBkpTree: () => ({ data: [], isLoading: false }),
  bkpCodesKey: () => ["bkp-codes"],
}));

vi.mock("@/features/projects/api", () => ({
  useProjects: () => ({ data: [], isLoading: false }),
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({
    accessToken: "test-token",
    user: { id: "user-1", email: "u@example.ch", display_name: "U" },
  }),
  AuthProvider: ({ children }: { children: ReactNode }) => children,
}));

// ---- Test fixtures ------------------------------------------------------- //

const OBJ_ID = "11111111-1111-1111-1111-111111111111";
const UNIT_ID = "22222222-2222-2222-2222-222222222222";
const TAG_A_ID = "33333333-3333-3333-3333-333333333333";
const TAG_B_ID = "44444444-4444-4444-4444-444444444444";
const NEW_ITEM_ID = "55555555-5555-5555-5555-555555555555";

const tagA = {
  id: TAG_A_ID,
  object_id: OBJ_ID,
  key: "raum",
  value: "kueche",
  color: null,
  created_at: "2026-01-01T00:00:00Z",
};
const tagB = {
  id: TAG_B_ID,
  object_id: OBJ_ID,
  key: "phase",
  value: "1",
  color: null,
  created_at: "2026-01-01T00:00:00Z",
};

const objectDetail = {
  id: OBJ_ID,
  name: "Demo",
  address: null,
  year_built: null,
  type: "sfh" as const,
  units: [
    {
      id: UNIT_ID,
      object_id: OBJ_ID,
      label: "EG",
      wertquote_permille: 1000,
      area_m2: null,
    },
  ],
};

function withProviders(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/objekte/${OBJ_ID}/kosten`]}>
        <Routes>
          <Route path="/objekte/:objectId/kosten" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ---- Tests --------------------------------------------------------------- //

describe("CostsPage tag assignment on create", () => {
  beforeEach(() => {
    tagCatalogue.length = 0;
    tagCatalogue.push(tagA, tagB);
    mockAssignTag.mockResolvedValue({
      tag_id: TAG_A_ID,
      target_type: "cost_item",
      target_id: NEW_ITEM_ID,
    });
    mockGetObject.mockResolvedValue(objectDetail);
    mockCreateCostItem.mockResolvedValue({
      id: NEW_ITEM_ID,
      object_id: OBJ_ID,
      bkp_code: null,
      project_id: null,
      npk_code: null,
      title: "Neue Position",
      description: null,
      status: "idea",
      priority: "med",
      planned_year: null,
      planned_amount_chf: "100.00",
      actual_amount_chf: null,
      actual_date: null,
      lifespan_years: null,
      warranty_until: null,
      scope: "shared",
      created_by: "user-1",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      allocations: [{ unit_id: UNIT_ID, share_permille: 1000 }],
      bkp_allocations: [],
      tag_ids: null,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("calls assignTag for each picked tag after create resolves", async () => {
    const { CostsPage } = await import("@/features/costs/CostsPage");
    render(withProviders(<CostsPage />));

    // Wait for the object to load then open the create drawer.
    await waitFor(() => {
      expect(screen.getByText("Demo")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Neue Kostenposition/i }));

    // Fill the minimum: title + planned amount. The drawer dialog is the
    // last-rendered region; constrain queries to its inputs to avoid the
    // filter widget's "Titel suchen" / etc.
    const titleInputs = screen.getAllByLabelText(/Titel/i);
    const titleInput = titleInputs[titleInputs.length - 1];
    if (!titleInput) throw new Error("title input not found");
    fireEvent.change(titleInput, { target: { value: "Neue Position" } });
    const plannedInput = screen.getByLabelText(/Geplant CHF/i);
    fireEvent.change(plannedInput, { target: { value: "100.00" } });

    // Pick two tags via the TagPicker inside the drawer. The filter widget
    // also embeds a TagPicker; the drawer renders later in DOM order so we
    // pick the last match.
    const tagInputs = screen.getAllByPlaceholderText(/Tag suchen/i);
    const tagInput = tagInputs[tagInputs.length - 1];
    if (!tagInput) throw new Error("tag input not found");
    fireEvent.focus(tagInput);
    fireEvent.change(tagInput, { target: { value: "raum" } });
    await waitFor(() => {
      // Use the chip rendered inside the dropdown option button.
      expect(screen.getAllByTestId(`tag-chip-${TAG_A_ID}`).length).toBeGreaterThan(0);
    });
    // The dropdown option <button> contains the chip; click that button.
    const chipA = screen.getAllByTestId(`tag-chip-${TAG_A_ID}`)[0];
    const btnA = chipA?.closest("button");
    if (!btnA) throw new Error("tag A dropdown option not found");
    fireEvent.click(btnA);
    fireEvent.focus(tagInput);
    fireEvent.change(tagInput, { target: { value: "phase" } });
    await waitFor(() => {
      expect(screen.getAllByTestId(`tag-chip-${TAG_B_ID}`).length).toBeGreaterThan(0);
    });
    const chipB = screen.getAllByTestId(`tag-chip-${TAG_B_ID}`)[0];
    const btnB = chipB?.closest("button");
    if (!btnB) throw new Error("tag B dropdown option not found");
    fireEvent.click(btnB);

    // Submit the form.
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Speichern/i }));
      // Yield so React processes the click + the create mutation's promise.
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(mockCreateCostItem).toHaveBeenCalledTimes(1);
    });
    // Both assignTag calls should be made, referencing the new item id and
    // the two picked tag ids.
    await waitFor(() => {
      expect(mockAssignTag).toHaveBeenCalledTimes(2);
    });
    const calls = mockAssignTag.mock.calls.map((c) => {
      const arg1 = c[1] as { target_id: string; target_type: string };
      return [c[0] as string, arg1.target_id, arg1.target_type] as const;
    });
    expect(calls).toEqual(
      expect.arrayContaining([
        [TAG_A_ID, NEW_ITEM_ID, "cost_item"],
        [TAG_B_ID, NEW_ITEM_ID, "cost_item"],
      ]),
    );
  });

  it("does not call assignTag when no tags were picked", async () => {
    const { CostsPage } = await import("@/features/costs/CostsPage");
    render(withProviders(<CostsPage />));

    await waitFor(() => {
      expect(screen.getByText("Demo")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Neue Kostenposition/i }));

    const titleInputs = screen.getAllByLabelText(/Titel/i);
    const titleInput = titleInputs[titleInputs.length - 1];
    if (!titleInput) throw new Error("title input not found");
    fireEvent.change(titleInput, { target: { value: "Ohne Tags" } });
    fireEvent.change(screen.getByLabelText(/Geplant CHF/i), {
      target: { value: "50.00" },
    });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Speichern/i }));
      // Yield so React processes the click + the create mutation's promise.
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(mockCreateCostItem).toHaveBeenCalledTimes(1);
    });
    expect(mockAssignTag).not.toHaveBeenCalled();
  });
});
