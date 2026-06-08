import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AllSuppliersPage } from "@/features/suppliers/AllSuppliersPage";
import { get, mockFetchByRoute, renderWithProviders } from "./budget/helpers";

const SUPPLIER_ROW = {
  id: "33333333-3333-3333-3333-333333333333",
  object_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  object_name: "Haus A",
  name: "Firma A",
  contact_email: "info@firma.ch",
  contact_phone: null,
  address: null,
  notes: null,
  archived_at: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("AllSuppliersPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders rows with name and parent object", async () => {
    mockFetchByRoute([
      {
        match: get("/suppliers"),
        respond: () => ({ body: [SUPPLIER_ROW] }),
      },
    ]);
    renderWithProviders(<AllSuppliersPage />);
    await waitFor(() =>
      expect(screen.getByText("Firma A")).toBeInTheDocument(),
    );
    expect(screen.getByText("Haus A")).toBeInTheDocument();
  });

  it("renders empty state", async () => {
    mockFetchByRoute([
      {
        match: get("/suppliers"),
        respond: () => ({ body: [] }),
      },
    ]);
    renderWithProviders(<AllSuppliersPage />);
    await waitFor(() =>
      expect(
        screen.getByText("Noch keine Lieferanten erfasst."),
      ).toBeInTheDocument(),
    );
  });
});
