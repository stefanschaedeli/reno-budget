import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TagPicker } from "@/components/TagPicker";
import type { Tag } from "@/features/tags/types";
import "@/i18n/i18n";

const OBJECT_ID = "00000000-0000-0000-0000-000000000001";

const existing: Tag[] = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    object_id: OBJECT_ID,
    key: "raum",
    value: "küche",
    color: null,
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "22222222-2222-2222-2222-222222222222",
    object_id: OBJECT_ID,
    key: "raum",
    value: "bad",
    color: null,
    created_at: "2026-01-01T00:00:00Z",
  },
];

function withProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

function setupFetch(
  handlers: Array<{ match: (url: string, init: RequestInit) => boolean; status?: number; body: unknown }>,
): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const realInit = init ?? {};
      const h = handlers.find((handler) => handler.match(url, realInit));
      if (!h) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: `unmatched ${url}` }), {
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

describe("TagPicker", () => {
  beforeEach(() => {
    setupFetch([
      {
        match: (url, init) =>
          (init.method ?? "GET") === "GET" && url.includes(`/objects/${OBJECT_ID}/tags`),
        body: existing,
      },
      {
        match: (url, init) =>
          init.method === "POST" && url.includes(`/objects/${OBJECT_ID}/tags`),
        body: {
          id: "33333333-3333-3333-3333-333333333333",
          object_id: OBJECT_ID,
          key: "raum",
          value: "schlafzimmer",
          color: null,
          created_at: "2026-01-01T00:00:00Z",
        },
      },
    ]);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("lists existing tags and lets the user select one", async () => {
    const onChange = vi.fn();
    render(
      withProviders(
        <TagPicker objectId={OBJECT_ID} value={[]} onChange={onChange} />,
      ),
    );
    const input = await screen.findByRole("textbox");
    fireEvent.focus(input);
    await waitFor(() =>
      expect(screen.getByText(/küche/)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText(/küche/).closest("button")!);
    expect(onChange).toHaveBeenCalledWith([existing[0]]);
  });

  it("offers Create-new when query is key:value and no match exists", async () => {
    const onChange = vi.fn();
    render(
      withProviders(
        <TagPicker objectId={OBJECT_ID} value={[]} onChange={onChange} />,
      ),
    );
    const input = await screen.findByRole("textbox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "raum:schlafzimmer" } });
    const createBtn = await screen.findByText(/Neuen Tag anlegen/);
    fireEvent.click(createBtn);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const call = onChange.mock.calls.at(-1) as [Tag[]];
    expect(call[0][0]?.key).toBe("raum");
    expect(call[0][0]?.value).toBe("schlafzimmer");
  });

  it("removes a selected chip on close-click", async () => {
    const onChange = vi.fn();
    render(
      withProviders(
        <TagPicker
          objectId={OBJECT_ID}
          value={[existing[0]!]}
          onChange={onChange}
        />,
      ),
    );
    const remove = await screen.findByLabelText(/Tag entfernen/);
    fireEvent.click(remove);
    expect(onChange).toHaveBeenCalledWith([]);
  });
});
