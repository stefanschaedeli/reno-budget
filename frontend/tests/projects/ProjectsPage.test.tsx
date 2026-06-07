import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ProjectsPage } from "@/features/projects/ProjectsPage";
import "@/i18n/i18n";

const OBJ_ID = "00000000-0000-0000-0000-000000000001";

const projectA = {
  id: "11111111-1111-1111-1111-111111111111",
  object_id: OBJ_ID,
  name: "Bad-Sanierung",
  description: null,
  status: "planned",
  planned_year: 2027,
  archived_at: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function setupFetch(handlers: Array<{ match: (url: string, init: RequestInit) => boolean; status?: number; body: unknown }>): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const realInit = init ?? {};
      const h = handlers.find((handler) => handler.match(url, realInit));
      if (!h) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: `unmatched ${url} (${realInit.method ?? "GET"})` }), {
            status: 500,
            headers: { "content-type": "application/json" },
          }),
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

function renderRoute(initial = `/objekte/${OBJ_ID}/projekte`) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/objekte/:objectId/projekte" element={<ProjectsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ProjectsPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders an empty state when no projects exist", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/objects/${OBJ_ID}/projects`),
        body: [],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/objects/${OBJ_ID}/cost-items`),
        body: [],
      },
    ]);
    renderRoute();
    await waitFor(() =>
      expect(screen.getByText(/Noch keine Projekte erfasst/)).toBeInTheDocument(),
    );
  });

  it("lists projects with status and planned year", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/objects/${OBJ_ID}/projects`),
        body: [projectA],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/objects/${OBJ_ID}/cost-items`),
        body: [],
      },
    ]);
    renderRoute();
    await waitFor(() =>
      expect(screen.getByTestId(`project-row-${projectA.id}`)).toBeInTheDocument(),
    );
    expect(screen.getByText("Bad-Sanierung")).toBeInTheDocument();
    expect(screen.getByText("2027")).toBeInTheDocument();
  });

  it("opens the create drawer when the New Project button is clicked", async () => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/objects/${OBJ_ID}/projects`),
        body: [],
      },
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/objects/${OBJ_ID}/cost-items`),
        body: [],
      },
    ]);
    renderRoute();
    await waitFor(() => screen.getByText(/Noch keine Projekte erfasst/));
    fireEvent.click(screen.getByText(/Neues Projekt/));
    expect(screen.getAllByText(/Neues Projekt/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/^Name/)).toBeInTheDocument();
  });
});
