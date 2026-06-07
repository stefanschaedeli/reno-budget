import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QuotesPanel } from "@/features/quotes/QuotesPanel";
import "@/i18n/i18n";

const OBJ_ID = "00000000-0000-0000-0000-000000000001";
const LOT_ID = "11111111-1111-1111-1111-111111111111";
const SUP_ID = "22222222-2222-2222-2222-222222222222";
const QUOTE_ID = "33333333-3333-3333-3333-333333333333";

const supplierA = {
  id: SUP_ID,
  object_id: OBJ_ID,
  name: "Acme AG",
  contact_email: null,
  contact_phone: null,
  address: null,
  notes: null,
  archived_at: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function mkQuote(id: string, status: string, amount = "12345.00") {
  return {
    id,
    lot_id: LOT_ID,
    supplier_id: SUP_ID,
    amount_chf: amount,
    received_at: "2026-06-01",
    valid_until: null,
    notes: null,
    status,
    created_by: null,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
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

function renderPanel(lotStatus = "tendering") {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <QuotesPanel lotId={LOT_ID} objectId={OBJ_ID} lotStatus={lotStatus} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("QuotesPanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists quotes and shows the awarded banner when applicable", async () => {
    const q = mkQuote(QUOTE_ID, "awarded");
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/lots/${LOT_ID}/quotes`),
        body: [q],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/objects/${OBJ_ID}/suppliers`),
        body: [supplierA],
      },
    ]);
    renderPanel("awarded");
    await waitFor(() =>
      expect(screen.getByTestId(`quote-row-${QUOTE_ID}`)).toBeInTheDocument(),
    );
    expect(screen.getByTestId("awarded-banner")).toBeInTheDocument();
  });

  it("calls the award endpoint when the user confirms", async () => {
    const initial = mkQuote(QUOTE_ID, "received");
    const awarded = mkQuote(QUOTE_ID, "awarded");
    let isAwarded = false;
    const awardCalls: string[] = [];
    vi.spyOn(window, "confirm").mockReturnValue(true);
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "POST" &&
          url.endsWith(`/lots/${LOT_ID}/quotes/${QUOTE_ID}/award`),
        body: (() => {
          awardCalls.push("called");
          isAwarded = true;
          return awarded;
        })(),
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/lots/${LOT_ID}/quotes`),
        get body() {
          return isAwarded ? [awarded] : [initial];
        },
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/objects/${OBJ_ID}/suppliers`),
        body: [supplierA],
      },
    ]);
    renderPanel("tendering");
    await waitFor(() =>
      expect(screen.getByTestId(`quote-row-${QUOTE_ID}`)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText(/^Vergeben$/));
    await waitFor(() => {
      expect(awardCalls.length).toBeGreaterThan(0);
    });
  });

  it("opens the add form when the user clicks 'Angebot erfassen'", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/lots/${LOT_ID}/quotes`),
        body: [],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/objects/${OBJ_ID}/suppliers`),
        body: [supplierA],
      },
    ]);
    renderPanel("tendering");
    await waitFor(() =>
      expect(screen.getByText(/Noch keine Angebote/)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText(/Angebot erfassen/));
    await waitFor(() =>
      expect(screen.getByPlaceholderText("12345.00")).toBeInTheDocument(),
    );
  });
});
