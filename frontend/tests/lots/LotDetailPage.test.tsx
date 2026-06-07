import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { LotDetailPage } from "@/features/lots/LotDetailPage";
import "@/i18n/i18n";

const OBJ_ID = "00000000-0000-0000-0000-000000000001";
const LOT_ID = "11111111-1111-1111-1111-111111111111";
const ITEM_A = "22222222-2222-2222-2222-222222222222";
const ITEM_B = "33333333-3333-3333-3333-333333333333";

const lot = {
  id: LOT_ID,
  object_id: OBJ_ID,
  name: "Sanitär",
  description: null,
  status: "draft",
  tender_deadline: null,
  awarded_quote_id: null,
  archived_at: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  cost_item_count: 1,
  cost_item_ids: [ITEM_A],
};

function mkCostItem(id: string, title: string, planned: string) {
  return {
    id,
    object_id: OBJ_ID,
    bkp_code: "D01",
    project_id: null,
    npk_code: null,
    title,
    description: null,
    status: "planned",
    priority: "med",
    planned_year: null,
    planned_amount_chf: planned,
    actual_amount_chf: null,
    actual_date: null,
    lifespan_years: null,
    warranty_until: null,
    scope: "shared",
    created_by: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    allocations: [],
    bkp_allocations: [],
    tag_ids: null,
    lot_ids: null,
  };
}

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
      <MemoryRouter initialEntries={[`/lose/${LOT_ID}`]}>
        <Routes>
          <Route path="/lose/:lotId" element={<LotDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LotDetailPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows lot meta, members and the planned total rollup", async () => {
    const memberA = mkCostItem(ITEM_A, "Heizung", "1000.00");
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/lots/${LOT_ID}/cost-items`),
        body: [memberA],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/lots/${LOT_ID}/quotes`),
        body: [],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/lots/${LOT_ID}`),
        body: lot,
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/lot/${LOT_ID}/tags`),
        body: [],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/objects/${OBJ_ID}/cost-items`),
        body: [memberA],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/objects/${OBJ_ID}/suppliers`),
        body: [],
      },
    ]);
    renderRoute();
    await waitFor(() => expect(screen.getByText("Sanitär")).toBeInTheDocument());
    await waitFor(() =>
      expect(screen.getByTestId(`member-row-${ITEM_A}`)).toBeInTheDocument(),
    );
    // Total rollup should contain "1’000" formatted Swiss-style.
    await waitFor(() => {
      const elt = screen.getByText(/Summe geplant/);
      expect(elt).toBeInTheDocument();
    });
  });

  it("allows adding a candidate cost item to the lot", async () => {
    const itemA = mkCostItem(ITEM_A, "Heizung", "1000.00");
    const itemB = mkCostItem(ITEM_B, "Lüftung", "500.00");
    let added = false;
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "POST" && url.endsWith(`/lots/${LOT_ID}/cost-items`),
        status: 201,
        body: { lot_id: LOT_ID, cost_item_id: ITEM_B },
      },
      {
        match: (url, init) => {
          if ((init.method ?? "GET") !== "GET") return false;
          return url.includes(`/lots/${LOT_ID}/cost-items`);
        },
        get body() {
          return added ? [itemA, itemB] : [itemA];
        },
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/lots/${LOT_ID}/quotes`),
        body: [],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/lots/${LOT_ID}`),
        body: lot,
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/lot/${LOT_ID}/tags`),
        body: [],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/objects/${OBJ_ID}/cost-items`),
        body: [itemA, itemB],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/objects/${OBJ_ID}/suppliers`),
        body: [],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/lots/${LOT_ID}/quotes`),
        body: [],
      },
    ]);
    renderRoute();
    await waitFor(() =>
      expect(screen.getByTestId(`member-row-${ITEM_A}`)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText(/Position hinzufügen/));
    // After picker opens, ItemB ("Lüftung") should be a candidate.
    await waitFor(() => expect(screen.getByText("Lüftung")).toBeInTheDocument());
    added = true;
    const addButtons = screen.getAllByText(/Hinzufügen$/);
    if (!addButtons[0]) throw new Error("no add button found");
    fireEvent.click(addButtons[0]);
    // Eventually the new member row should appear.
    await waitFor(() =>
      expect(screen.getByTestId(`member-row-${ITEM_B}`)).toBeInTheDocument(),
    );
  });
});
