import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import type { ReactElement } from "react";
import "@/i18n/i18n";

export interface RouteHandler {
  match: (url: string, init: RequestInit) => boolean;
  respond: (
    url: string,
    init: RequestInit,
  ) => { status?: number; body: unknown };
}

export function mockFetchByRoute(handlers: RouteHandler[]): void {
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
      const handler = handlers.find((h) => h.match(url, realInit));
      if (!handler) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: `unmatched ${url}` }), {
            status: 500,
            headers: { "content-type": "application/json" },
          }),
        );
      }
      const { status = 200, body } = handler.respond(url, realInit);
      return Promise.resolve(
        new Response(JSON.stringify(body), {
          status,
          headers: { "content-type": "application/json" },
        }),
      );
    }),
  );
}

export function renderWithProviders(
  ui: ReactElement,
  opts?: { initialRoute?: string },
): RenderResult & { queryClient: QueryClient } {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const result = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[opts?.initialRoute ?? "/"]}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return Object.assign(result, { queryClient });
}

export function get(path: string): RouteHandler["match"] {
  return (url, init) =>
    (init.method ?? "GET") === "GET" && url.includes(path);
}

export function patch(path: string): RouteHandler["match"] {
  return (url, init) => init.method === "PATCH" && url.includes(path);
}
