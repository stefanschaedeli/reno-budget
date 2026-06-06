import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BkpCodePicker } from "@/features/costs/BkpCodePicker";
import "@/i18n/i18n";

const { mockTree } = vi.hoisted(() => ({
  mockTree: [
    {
      code: "C",
      parent_code: null,
      level: 1,
      label_de: "Konstruktion Gebäude",
      description: null,
      is_seed: true,
      children: [
        {
          code: "C2",
          parent_code: "C",
          level: 2,
          label_de: "Aussenwandkonstruktion",
          description: null,
          is_seed: true,
          children: [
            {
              code: "C2.1",
              parent_code: "C2",
              level: 3,
              label_de: "Fenster",
              description: null,
              is_seed: true,
              children: [],
            },
          ],
        },
      ],
    },
    {
      code: "D",
      parent_code: null,
      level: 1,
      label_de: "Technik",
      description: null,
      is_seed: true,
      children: [],
    },
  ],
}));

vi.mock("@/api/bkp", () => ({
  useBkpTree: () => ({
    data: mockTree,
    isLoading: false,
    isError: false,
  }),
  fetchBkpTree: () => Promise.resolve(mockTree),
  fetchBkpCodes: () => Promise.resolve([]),
  useBkpCodes: () => ({ data: [], isLoading: false, isError: false }),
}));

function renderPicker(props: {
  value: string | null;
  onChange: (c: string) => void;
}): void {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <BkpCodePicker value={props.value} onChange={props.onChange} />
    </QueryClientProvider>,
  );
}

describe("BkpCodePicker", () => {
  it("renders top-level nodes from the catalog", async () => {
    renderPicker({ value: null, onChange: () => {} });
    await waitFor(() =>
      expect(screen.getByText("Konstruktion Gebäude")).toBeInTheDocument(),
    );
    expect(screen.getByText("Technik")).toBeInTheDocument();
  });

  it("filters the tree by search term", async () => {
    renderPicker({ value: null, onChange: () => {} });
    await waitFor(() =>
      expect(screen.getByText("Konstruktion Gebäude")).toBeInTheDocument(),
    );
    const search = screen.getByLabelText(/Code oder Bezeichnung suchen/);
    fireEvent.change(search, { target: { value: "Fenster" } });
    await waitFor(() => {
      expect(screen.getByText("Fenster")).toBeInTheDocument();
      expect(screen.queryByText("Technik")).not.toBeInTheDocument();
    });
  });

  it("emits onChange when a code is clicked", async () => {
    const onChange = vi.fn();
    renderPicker({ value: null, onChange });
    await waitFor(() =>
      expect(screen.getByText("Konstruktion Gebäude")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText("Konstruktion Gebäude"));
    expect(onChange).toHaveBeenCalledWith("C");
  });
});
