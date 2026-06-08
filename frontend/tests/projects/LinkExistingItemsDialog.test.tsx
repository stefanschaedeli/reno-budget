// frontend/tests/projects/LinkExistingItemsDialog.test.tsx
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n/i18n";

vi.mock("@/api/costs", async () => {
  return {
    useCostItems: vi.fn(),
    updateCostItem: vi.fn().mockResolvedValue({}),
  };
});

import { useCostItems, updateCostItem } from "@/api/costs";
import { LinkExistingItemsDialog } from "@/features/projects/LinkExistingItemsDialog";

function withProviders(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>{ui}</I18nextProvider>
    </QueryClientProvider>
  );
}

const items = [
  { id: "c1", title: "Boden Bad", project_id: null },
  { id: "c2", title: "Sanitär Bad", project_id: null },
];

beforeEach(() => {
  (useCostItems as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    data: items,
    isLoading: false,
    isError: false,
  });
  (updateCostItem as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({});
});

describe("LinkExistingItemsDialog", () => {
  it("lists unassigned items (called with project_id_is_null)", () => {
    render(
      withProviders(
        <LinkExistingItemsDialog
          objectId="o1"
          projectId="p1"
          onClose={vi.fn()}
          onLinked={vi.fn()}
        />,
      ),
    );
    expect(screen.getByText("Boden Bad")).toBeInTheDocument();
    expect(screen.getByText("Sanitär Bad")).toBeInTheDocument();
    const callArgs = (useCostItems as unknown as ReturnType<typeof vi.fn>).mock
      .calls[0]!;
    expect(callArgs[0]).toBe("o1");
    expect(callArgs[1]).toMatchObject({ project_id_is_null: true });
  });

  it("links selected items on confirm", async () => {
    const onLinked = vi.fn();
    render(
      withProviders(
        <LinkExistingItemsDialog
          objectId="o1"
          projectId="p1"
          onClose={vi.fn()}
          onLinked={onLinked}
        />,
      ),
    );
    fireEvent.click(screen.getByLabelText("Boden Bad"));
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfen/i }));
    await waitFor(() => expect(onLinked).toHaveBeenCalled());
    expect(updateCostItem).toHaveBeenCalledTimes(1);
  });
});
