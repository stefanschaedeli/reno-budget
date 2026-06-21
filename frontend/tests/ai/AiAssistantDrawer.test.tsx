import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AiAssistantDrawer } from "@/features/ai/AiAssistantDrawer";

import { get, mockFetchByRoute, renderWithProviders } from "../budget/helpers";
import type { RouteHandler } from "../budget/helpers";

const OBJ = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const PROJ = "11111111-1111-1111-1111-111111111111";

function post(path: string): RouteHandler["match"] {
  return (url, init) => init.method === "POST" && url.includes(path);
}

const ESTIMATE_ARTIFACT = {
  id: "art-est",
  session_id: "sess-1",
  step: "estimate",
  status: "draft",
  output: {
    currency: "CHF",
    total_chf: "30000.00",
    line_items: [
      {
        label: "Eindeckung",
        amount_chf: "30000.00",
        assumptions: "120 m² Ziegel",
        confidence: "medium",
      },
    ],
    notes: null,
  },
  validation: { ok: true, findings: [] },
  created_at: "2026-06-21T10:00:00Z",
  updated_at: "2026-06-21T10:00:00Z",
};

const SESSION = {
  id: "sess-1",
  object_id: OBJ,
  project_id: PROJ,
  status: "active",
  project_type: "roof",
  answers: { area_m2: 120 },
  created_at: "2026-06-21T10:00:00Z",
  updated_at: "2026-06-21T10:00:00Z",
  artifacts: [ESTIMATE_ARTIFACT],
};

describe("AiAssistantDrawer", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("blocks estimate/question/bkp steps until a project type is set", async () => {
    const noType = { ...SESSION, project_type: null, artifacts: [] };
    mockFetchByRoute([
      { match: get("/ai/session"), respond: () => ({ body: noType }) },
    ]);
    renderWithProviders(
      <AiAssistantDrawer objectId={OBJ} projectId={PROJ} onClose={vi.fn()} />,
    );

    // The estimate action button is disabled while the type is unknown.
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Schätzung erstellen" }),
      ).toBeDisabled(),
    );
    // The classify action remains available.
    expect(
      screen.getByRole("button", { name: "Projekttyp bestimmen" }),
    ).toBeEnabled();
  });

  it("renders an existing estimate draft with total and accept button", async () => {
    mockFetchByRoute([
      { match: get("/ai/session"), respond: () => ({ body: SESSION }) },
    ]);
    renderWithProviders(
      <AiAssistantDrawer objectId={OBJ} projectId={PROJ} onClose={vi.fn()} />,
    );

    await waitFor(() =>
      expect(screen.getByText("Eindeckung")).toBeInTheDocument(),
    );
    // Money rendered (CHF formatted).
    expect(screen.getAllByText(/30’?000|30,000|30'000/).length).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: "Übernehmen" }),
    ).toBeEnabled();
  });

  it("accepting a valid draft calls the accept endpoint", async () => {
    const acceptCalls: string[] = [];
    mockFetchByRoute([
      { match: get("/ai/session"), respond: () => ({ body: SESSION }) },
      {
        match: post("/artifacts/art-est/accept"),
        respond: (url) => {
          acceptCalls.push(url);
          return { body: { ...ESTIMATE_ARTIFACT, status: "accepted" } };
        },
      },
    ]);
    renderWithProviders(
      <AiAssistantDrawer objectId={OBJ} projectId={PROJ} onClose={vi.fn()} />,
    );

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Übernehmen" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Übernehmen" }));

    await waitFor(() => expect(acceptCalls.length).toBe(1));
  });

  it("disables accept when the draft failed validation", async () => {
    const failed = {
      ...SESSION,
      artifacts: [
        {
          ...ESTIMATE_ARTIFACT,
          id: "art-bad",
          validation: {
            ok: false,
            findings: [
              { layer: 1, severity: "error", message: "Summe stimmt nicht", target: null },
            ],
          },
        },
      ],
    };
    mockFetchByRoute([
      { match: get("/ai/session"), respond: () => ({ body: failed }) },
    ]);
    renderWithProviders(
      <AiAssistantDrawer objectId={OBJ} projectId={PROJ} onClose={vi.fn()} />,
    );

    await waitFor(() =>
      expect(screen.getByText("Summe stimmt nicht")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Übernehmen" })).toBeDisabled();
  });
});
