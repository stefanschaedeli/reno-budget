import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SuppliersPage } from "@/features/suppliers/SuppliersPage";
import "@/i18n/i18n";

const OBJ_ID = "00000000-0000-0000-0000-000000000001";

const supplierA = {
  id: "11111111-1111-1111-1111-111111111111",
  object_id: OBJ_ID,
  name: "Acme AG",
  contact_email: "info@acme.example",
  contact_phone: "+41 44 555 11 22",
  address: null,
  notes: null,
  archived_at: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
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

function renderRoute() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/objekte/${OBJ_ID}/lieferanten`]}>
        <Routes>
          <Route
            path="/objekte/:objectId/lieferanten"
            element={<SuppliersPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SuppliersPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders an empty state when no suppliers exist", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/objects/${OBJ_ID}/suppliers`),
        body: [],
      },
    ]);
    renderRoute();
    await waitFor(() =>
      expect(
        screen.getByText(/Noch keine Lieferanten erfasst/),
      ).toBeInTheDocument(),
    );
  });

  it("renders supplier rows from the API", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/objects/${OBJ_ID}/suppliers`),
        body: [supplierA],
      },
    ]);
    renderRoute();
    await waitFor(() =>
      expect(screen.getByText("Acme AG")).toBeInTheDocument(),
    );
    expect(screen.getByText("info@acme.example")).toBeInTheDocument();
  });
});
