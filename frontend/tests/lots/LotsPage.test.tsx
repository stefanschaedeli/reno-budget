import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { LotsPage } from "@/features/lots/LotsPage";
import "@/i18n/i18n";

const OBJ_ID = "00000000-0000-0000-0000-000000000001";

const lotA = {
  id: "11111111-1111-1111-1111-111111111111",
  object_id: OBJ_ID,
  name: "Sanitär-Paket",
  description: null,
  status: "draft",
  tender_deadline: null,
  awarded_quote_id: null,
  archived_at: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  cost_item_count: 3,
  cost_item_ids: null,
};

interface Handler {
  match: (url: string, init: RequestInit) => boolean;
  status?: number;
  body: unknown;
}

function setupFetch(handlers: Handler[]): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      const realInit = init ?? {};
      const h = handlers.find((handler) => handler.match(url, realInit));
      if (!h) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ detail: `unmatched ${url} (${realInit.method ?? "GET"})` }),
            { status: 500, headers: { "content-type": "application/json" } },
          ),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify(h.body), {
          status: h.status ?? 200,
          headers: { "content-type": "application/json" },
        }),
      );
    }),
  );
}

function renderRoute(initial = `/objekte/${OBJ_ID}/lose`) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/objekte/:objectId/lose" element={<LotsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LotsPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders an empty state when no lots exist", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/objects/${OBJ_ID}/lots`),
        body: [],
      },
    ]);
    renderRoute();
    await waitFor(() =>
      expect(screen.getByText(/Noch keine Lose erfasst/)).toBeInTheDocument(),
    );
  });

  it("lists lots with status and item count", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/objects/${OBJ_ID}/lots`),
        body: [lotA],
      },
    ]);
    renderRoute();
    await waitFor(() =>
      expect(screen.getByTestId(`lot-row-${lotA.id}`)).toBeInTheDocument(),
    );
    expect(screen.getByText("Sanitär-Paket")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("opens the create drawer when the New Lot button is clicked", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/objects/${OBJ_ID}/lots`),
        body: [],
      },
    ]);
    renderRoute();
    await waitFor(() => screen.getByText(/Noch keine Lose erfasst/));
    fireEvent.click(screen.getByText(/Neues Los/));
    expect(screen.getAllByText(/Neues Los/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/^Name/)).toBeInTheDocument();
  });
});
