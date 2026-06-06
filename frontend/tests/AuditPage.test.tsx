import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@/i18n/i18n";
import { ApiError } from "@/api/client";

const mockListObject = vi.fn();
const mockListGlobal = vi.fn();

vi.mock("@/features/audit/api", () => ({
  listObjectAudit: (...a: unknown[]): unknown => mockListObject(...a) as unknown,
  listGlobalAudit: (...a: unknown[]): unknown => mockListGlobal(...a) as unknown,
}));

vi.mock("@/features/auth/AuthContext", () => ({
  useAuth: () => ({
    accessToken: "test-token",
    user: { id: "user-1", email: "u@example.ch", display_name: "U" },
  }),
  AuthProvider: ({ children }: { children: ReactNode }) => children,
}));

import { GlobalAuditPage, ObjectAuditPage } from "@/features/audit/AuditPage";

const sampleEvent = {
  id: "11111111-1111-1111-1111-111111111111",
  created_at: "2026-06-06T12:00:00Z",
  actor_user_id: "u1",
  actor_email: "owner@example.ch",
  action: "cost_item.create",
  object_id: "obj-1",
  target_type: "cost_item",
  target_id: "ci-1",
  summary: "Heizung erstellt",
  payload: null,
  ip_address: null,
  user_agent: null,
};

function renderObject(): void {
  render(
    <MemoryRouter initialEntries={["/objekte/obj-1/audit"]}>
      <Routes>
        <Route path="/objekte/:id/audit" element={<ObjectAuditPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AuditPage", () => {
  beforeEach(() => {
    mockListObject.mockReset();
    mockListGlobal.mockReset();
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders an empty state for an object with no events", async () => {
    mockListObject.mockResolvedValueOnce({ items: [], next_before: null });
    renderObject();
    await waitFor(() => {
      expect(screen.getByText(/Noch keine Einträge/)).toBeInTheDocument();
    });
  });

  it("renders events with German action labels and actor email", async () => {
    mockListObject.mockResolvedValueOnce({
      items: [sampleEvent],
      next_before: null,
    });
    renderObject();
    await waitFor(() => {
      expect(screen.getByText(/Kostenposition erstellt/)).toBeInTheDocument();
    });
    expect(screen.getByText("owner@example.ch")).toBeInTheDocument();
    expect(screen.getByText("Heizung erstellt")).toBeInTheDocument();
  });

  it("shows a forbidden message when the API returns 403", async () => {
    mockListObject.mockRejectedValueOnce(new ApiError(403, "forbidden"));
    renderObject();
    await waitFor(() => {
      expect(
        screen.getByText(/Nur Eigentümer können den Verlauf einsehen/),
      ).toBeInTheDocument();
    });
  });

  it("loads more events when the cursor is non-null", async () => {
    mockListObject
      .mockResolvedValueOnce({ items: [sampleEvent], next_before: "2026-06-05T00:00:00Z" })
      .mockResolvedValueOnce({
        items: [{ ...sampleEvent, id: "2", summary: "Zweites Ereignis" }],
        next_before: null,
      });
    renderObject();
    await waitFor(() => {
      expect(screen.getByText("Heizung erstellt")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Weitere laden/));
    await waitFor(() => {
      expect(screen.getByText("Zweites Ereignis")).toBeInTheDocument();
    });
    // "Weitere laden" button disappears after the last page.
    expect(screen.queryByText(/Weitere laden/)).not.toBeInTheDocument();
  });

  it("renders the global view title in the superuser mode", async () => {
    mockListGlobal.mockResolvedValueOnce({ items: [], next_before: null });
    render(
      <MemoryRouter>
        <GlobalAuditPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText(/Globales Audit-Log/)).toBeInTheDocument();
    });
  });
});
