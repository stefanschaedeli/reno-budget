import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ObjectProjectsSection } from "@/features/projects/ObjectProjectsSection";
import "@/i18n/i18n";

const OBJ_ID = "00000000-0000-0000-0000-000000000001";

const projectA = {
  id: "11111111-1111-1111-1111-111111111111",
  object_id: OBJ_ID,
  name: "Bad-Sanierung",
  description: null,
  status: "planned",
  planned_year: 2027,
  rough_estimate_chf: "50000.00",
  archived_at: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function setupFetch(
  handlers: Array<{
    match: (url: string, init: RequestInit) => boolean;
    status?: number;
    body: unknown;
  }>,
): void {
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
            JSON.stringify({
              detail: `unmatched ${url} (${realInit.method ?? "GET"})`,
            }),
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

function renderSection() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/objekte/${OBJ_ID}`]}>
        <ObjectProjectsSection objectId={OBJ_ID} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ObjectProjectsSection", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders an empty state when the object has no projects", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/objects/${OBJ_ID}/projects`),
        body: [],
      },
    ]);
    renderSection();
    await waitFor(() =>
      expect(
        screen.getByText(/Noch keine Projekte\. Lege ein Projekt an/),
      ).toBeInTheDocument(),
    );
  });

  it("lists projects with status, Grobschätzung and planned year", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/objects/${OBJ_ID}/projects`),
        body: [projectA],
      },
    ]);
    renderSection();
    await waitFor(() =>
      expect(screen.getByTestId(`project-row-${projectA.id}`)).toBeInTheDocument(),
    );
    expect(screen.getByText("Bad-Sanierung")).toBeInTheDocument();
    expect(screen.getByText("2027")).toBeInTheDocument();
    // CHF formatter renders "50’000.00" (de-CH).
    expect(screen.getByText(/50/)).toBeInTheDocument();
  });

  it("opens the create drawer when the New Project button is clicked", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" &&
          url.includes(`/objects/${OBJ_ID}/projects`),
        body: [],
      },
    ]);
    renderSection();
    await waitFor(() => screen.getByText(/Noch keine Projekte/));
    fireEvent.click(screen.getByRole("button", { name: /Neues Projekt/ }));
    expect(screen.getByLabelText(/^Name/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Grobschätzung/)).toBeInTheDocument();
  });
});
