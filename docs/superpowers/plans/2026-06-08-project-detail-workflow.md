# Project Detail Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework `ProjectDetailPage` so users can see and edit the Grobschätzung as a top-level budget card, add new cost items directly to the project, and link existing unassigned cost items — supporting the Idee → Grobschätzung → Kostenplanung maturity ladder.

**Architecture:** One small backend addition (`project_id_is_null` filter on the cost-items list endpoint) plus a frontend refactor of `ProjectDetailPage` into three composed sections: `BudgetCard` (inline-edit Grobschätzung + variance), `ProjectCostItemsSection` (table + Neue Position + Verknüpfen dialog), and a collapsible Details panel wrapping the existing `ProjectForm`.

**Tech Stack:** Backend — FastAPI, SQLAlchemy, Pydantic v2, pytest-asyncio. Frontend — React + TS + Vite, TanStack Query, react-i18next, Zod, Tailwind, Vitest + React Testing Library.

**Spec:** `docs/superpowers/specs/2026-06-08-project-detail-workflow-design.md`

---

## File map

**Backend (modify):**
- `backend/app/schemas/cost.py` — add `project_id_is_null: bool` to `CostItemFilter` + cross-field validator.
- `backend/app/services/cost_items.py` — extend `_apply_filter` to honour the new flag.
- `backend/tests/integration/test_cost_items_filter_project_null.py` (create) — covers the new filter.

**Frontend (modify):**
- `frontend/src/features/costs/types.ts` — add `project_id_is_null?: boolean | undefined` to `CostItemFilters`.
- `frontend/src/api/costs.ts` — serialize the new field in `filtersToQuery`.
- `frontend/src/features/projects/ProjectDetailPage.tsx` — replace body with composed sections.
- `frontend/src/i18n/locales/de.ts` — new translation keys (also EN counterpart).
- `frontend/src/i18n/locales/en.ts` — same keys, EN strings.
- `frontend/tests/projects/ProjectDetailPage.test.tsx` — extend existing tests.

**Frontend (create):**
- `frontend/src/features/projects/BudgetCard.tsx` — Grobschätzung + planned-total + Differenz + bar.
- `frontend/src/features/projects/ProjectCostItemsSection.tsx` — table + two action buttons + create drawer.
- `frontend/src/features/projects/LinkExistingItemsDialog.tsx` — picker modal listing unassigned items.
- `frontend/tests/projects/BudgetCard.test.tsx`
- `frontend/tests/projects/LinkExistingItemsDialog.test.tsx`

---

## Task 1: Backend — add `project_id_is_null` filter field

**Files:**
- Modify: `backend/app/schemas/cost.py:244-270`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/integration/test_cost_items_filter_project_null.py`:

```python
"""Tests for the ``project_id_is_null`` filter on the cost-items list endpoint."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _seed(client: AsyncClient, object_id: uuid.UUID) -> tuple[str, str, str]:
    """Create a project and three cost items: one linked, two unlinked."""
    p_resp = await client.post(
        f"/api/v1/objects/{object_id}/projects",
        json={"name": "Bad-Sanierung", "status": "idea"},
    )
    assert p_resp.status_code == 201, p_resp.text
    project_id = p_resp.json()["id"]

    async def _mk(title: str, project: str | None) -> str:
        r = await client.post(
            f"/api/v1/objects/{object_id}/cost-items",
            json={
                "title": title,
                "status": "idea",
                "priority": "med",
                "scope": "shared",
                "project_id": project,
            },
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    assigned = await _mk("Linked item", project_id)
    free_a = await _mk("Free A", None)
    free_b = await _mk("Free B", None)
    return assigned, free_a, free_b


async def test_filter_only_unassigned_returns_null_project_items(
    authed_client: AsyncClient, owned_object_id: uuid.UUID
) -> None:
    assigned, free_a, free_b = await _seed(authed_client, owned_object_id)
    r = await authed_client.get(
        f"/api/v1/objects/{owned_object_id}/cost-items",
        params={"project_id_is_null": "true"},
    )
    assert r.status_code == 200, r.text
    ids = {row["id"] for row in r.json()}
    assert assigned not in ids
    assert {free_a, free_b}.issubset(ids)


async def test_filter_rejects_both_project_id_and_null_flag(
    authed_client: AsyncClient, owned_object_id: uuid.UUID
) -> None:
    r = await authed_client.get(
        f"/api/v1/objects/{owned_object_id}/cost-items",
        params={
            "project_id": str(uuid.uuid4()),
            "project_id_is_null": "true",
        },
    )
    assert r.status_code == 422, r.text
```

> If `authed_client` / `owned_object_id` fixture names differ in this repo, check `backend/tests/conftest.py` for the actual names and rename references accordingly.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/integration/test_cost_items_filter_project_null.py -v`
Expected: FAIL — the filter field doesn't exist; both tests either 200 with wrong contents or pass when they shouldn't.

- [ ] **Step 3: Add field + validator to `CostItemFilter`**

In `backend/app/schemas/cost.py`, change the `CostItemFilter` class (currently ending at the `include_lot_ids` line) to add a new field and a model-level validator:

```python
class CostItemFilter(BaseModel):
    """Query-string filter set for the list endpoint.

    All fields are optional; combining them is AND-ed. ``bkp_code`` is a
    *prefix* match so callers can request "everything under D" with a single
    character; this matches the way the eBKP-H tree is browsed in the UI.
    """

    status: CostItemStatus | None = None
    priority: CostItemPriority | None = None
    planned_year: int | None = Field(default=None, ge=1900, le=2200)
    bkp_code: str | None = Field(default=None, min_length=1, max_length=16)
    unit_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    # Phase 12: surface items that haven't been assigned to any project yet.
    # Mutually exclusive with ``project_id``.
    project_id_is_null: bool = False
    tag_id: list[uuid.UUID] | None = Field(default=None)
    lot_id: uuid.UUID | None = None
    q: str | None = Field(default=None, max_length=200)
    sort: str | None = Field(default=None, max_length=64)
    include_tag_ids: bool = False
    include_lot_ids: bool = False

    @model_validator(mode="after")
    def _project_filters_mutually_exclusive(self) -> "CostItemFilter":
        if self.project_id is not None and self.project_id_is_null:
            raise ValueError(
                "project_id and project_id_is_null are mutually exclusive",
            )
        return self
```

Add to the imports at the top of `backend/app/schemas/cost.py` (if not already present):

```python
from pydantic import BaseModel, Field, model_validator
```

- [ ] **Step 4: Honour the flag in `_apply_filter`**

In `backend/app/services/cost_items.py`, find `_apply_filter` (around line 556) and add after the existing `project_id` check (around line 571):

```python
    if filters.project_id_is_null and item.project_id is not None:
        return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/integration/test_cost_items_filter_project_null.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Run the full backend suite to confirm no regression**

Run: `cd backend && pytest -x`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/cost.py backend/app/services/cost_items.py backend/tests/integration/test_cost_items_filter_project_null.py
git commit -m "feat(api): project_id_is_null filter on cost-items list"
```

---

## Task 2: Frontend — extend `CostItemFilters` type + query serializer

**Files:**
- Modify: `frontend/src/features/costs/types.ts:176-192`
- Modify: `frontend/src/api/costs.ts:32-55`

- [ ] **Step 1: Extend the TS interface**

In `frontend/src/features/costs/types.ts`, edit the `CostItemFilters` interface (currently ends with `include_lot_ids?: boolean | undefined`) to add:

```typescript
  /** When true, list endpoint returns only cost items with no project_id. */
  project_id_is_null?: boolean | undefined;
```

(Place it directly under the existing `project_id?: string | null | undefined;` line for locality.)

- [ ] **Step 2: Serialize it in the query-string builder**

In `frontend/src/api/costs.ts`, inside `filtersToQuery`, directly after the existing `if (filters.project_id) params.set("project_id", filters.project_id);` line, add:

```typescript
  if (filters.project_id_is_null) params.set("project_id_is_null", "true");
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/costs/types.ts frontend/src/api/costs.ts
git commit -m "feat(api-client): serialize project_id_is_null filter"
```

---

## Task 3: Frontend — i18n keys for the new UI

**Files:**
- Modify: `frontend/src/i18n/locales/de.ts` (projects block around lines 430-459)
- Modify: `frontend/src/i18n/locales/en.ts` (same block)

- [ ] **Step 1: Replace the `projects.costItems` block (de.ts)**

In `frontend/src/i18n/locales/de.ts`, replace the existing `costItems:` block under `projects:` with:

```typescript
    costItems: {
      title: "Kostenpositionen in diesem Projekt",
      empty:
        "Noch keine Positionen. Beginnen Sie mit \"Neue Position\" oder verknüpfen Sie bestehende.",
      add: "Neue Position",
      link: "Bestehende Position verknüpfen",
      remove: "Von Projekt entfernen",
      removeConfirm: "Position aus diesem Projekt entfernen?",
      linkDialog: {
        title: "Bestehende Positionen verknüpfen",
        empty: "Keine unverknüpften Positionen auf diesem Objekt.",
        search: "Titel suchen…",
        confirm: "Verknüpfen",
        cancel: "Abbrechen",
        selected: "{{count}} ausgewählt",
      },
    },
```

Then, still under `projects:`, add a new sibling block (after `costItems`):

```typescript
    budget: {
      heading: "Budget",
      estimate: "Grobschätzung",
      planned: "Geplant aus Positionen",
      diff: "Differenz",
      addEstimate: "Grobschätzung hinzufügen",
      edit: "Bearbeiten",
      save: "Speichern",
      cancel: "Abbrechen",
      noEstimate: "Keine Grobschätzung erfasst",
      percentOfEstimate: "{{percent}} % der Grobschätzung",
    },
    details: {
      heading: "Details",
      show: "Details anzeigen",
      hide: "Details ausblenden",
    },
```

- [ ] **Step 2: Mirror the keys in en.ts**

In `frontend/src/i18n/locales/en.ts`, add the same key shape under `projects:` (overwrite the existing `costItems` block and add new `budget`, `details` blocks):

```typescript
    costItems: {
      title: "Cost items in this project",
      empty:
        "No items yet. Start with \"New item\" or link existing items.",
      add: "New item",
      link: "Link existing item",
      remove: "Remove from project",
      removeConfirm: "Remove item from this project?",
      linkDialog: {
        title: "Link existing items",
        empty: "No unlinked items on this object.",
        search: "Search title…",
        confirm: "Link",
        cancel: "Cancel",
        selected: "{{count}} selected",
      },
    },
    budget: {
      heading: "Budget",
      estimate: "Rough estimate",
      planned: "Planned from items",
      diff: "Difference",
      addEstimate: "Add rough estimate",
      edit: "Edit",
      save: "Save",
      cancel: "Cancel",
      noEstimate: "No rough estimate recorded",
      percentOfEstimate: "{{percent}}% of rough estimate",
    },
    details: {
      heading: "Details",
      show: "Show details",
      hide: "Hide details",
    },
```

- [ ] **Step 3: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/locales/de.ts frontend/src/i18n/locales/en.ts
git commit -m "i18n: add project budget + costItems action keys"
```

---

## Task 4: Frontend — `BudgetCard` component (failing test first)

**Files:**
- Create: `frontend/src/features/projects/BudgetCard.tsx`
- Create: `frontend/tests/projects/BudgetCard.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/projects/BudgetCard.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";
import { BudgetCard } from "@/features/projects/BudgetCard";

const baseProject = {
  id: "p1",
  object_id: "o1",
  name: "Test",
  description: null,
  status: "idea" as const,
  planned_year: null,
  rough_estimate_chf: null as string | number | null,
  archived_at: null,
  created_by: null,
  created_at: "",
  updated_at: "",
};

function withProviders(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>{ui}</I18nextProvider>
    </QueryClientProvider>
  );
}

describe("BudgetCard", () => {
  it("shows empty state when rough_estimate_chf is null", () => {
    render(
      withProviders(
        <BudgetCard project={baseProject} plannedTotal={0} onEstimateSaved={vi.fn()} />,
      ),
    );
    expect(screen.getByText(/Grobschätzung hinzufügen/i)).toBeInTheDocument();
  });

  it("shows planned total and difference (over)", () => {
    render(
      withProviders(
        <BudgetCard
          project={{ ...baseProject, rough_estimate_chf: "80000" }}
          plannedTotal={83200}
          onEstimateSaved={vi.fn()}
        />,
      ),
    );
    expect(screen.getByText(/80['’ ]?000/)).toBeInTheDocument();
    expect(screen.getByText(/83['’ ]?200/)).toBeInTheDocument();
    // Differenz: +3'200, marked red
    const diffNode = screen.getByTestId("budget-diff");
    expect(diffNode.textContent).toMatch(/3['’ ]?200/);
    expect(diffNode.className).toMatch(/red/);
  });

  it("opens inline editor on edit click", () => {
    render(
      withProviders(
        <BudgetCard
          project={{ ...baseProject, rough_estimate_chf: "80000" }}
          plannedTotal={0}
          onEstimateSaved={vi.fn()}
        />,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: /Bearbeiten/i }));
    expect(screen.getByRole("spinbutton")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/projects/BudgetCard.test.tsx`
Expected: FAIL — cannot resolve `@/features/projects/BudgetCard`.

- [ ] **Step 3: Implement `BudgetCard.tsx`**

Create `frontend/src/features/projects/BudgetCard.tsx`:

```typescript
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { formatChf } from "@/features/costs/types";
import { useUpdateProject } from "./api";
import type { Project } from "./types";

export interface BudgetCardProps {
  project: Project;
  /** Sum of planned_amount_chf across this project's cost items. */
  plannedTotal: number;
  onEstimateSaved?: (() => void) | undefined;
}

function toNumberOrNull(v: string | number | null): number | null {
  if (v === null || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

export function BudgetCard({
  project,
  plannedTotal,
  onEstimateSaved,
}: BudgetCardProps): JSX.Element {
  const { t } = useTranslation();
  const estimate = toNumberOrNull(project.rough_estimate_chf);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string>(
    estimate != null ? String(estimate) : "",
  );
  const updateMut = useUpdateProject(project.id);

  const diff = estimate != null ? plannedTotal - estimate : null;
  const percent =
    estimate != null && estimate > 0
      ? Math.round((plannedTotal / estimate) * 100)
      : null;
  const over = diff != null && diff > 0;

  const save = async () => {
    await updateMut.mutateAsync({
      rough_estimate_chf: draft.trim() === "" ? null : draft.trim(),
    });
    setEditing(false);
    onEstimateSaved?.();
  };

  return (
    <section className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-medium uppercase tracking-wide text-slate-500">
        {t("projects.budget.heading")}
      </h3>

      {estimate == null && !editing && (
        <div className="flex items-center justify-between">
          <p className="text-slate-500">{t("projects.budget.noEstimate")}</p>
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
          >
            {t("projects.budget.addEstimate")}
          </button>
        </div>
      )}

      {(estimate != null || editing) && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-slate-500">
                {t("projects.budget.estimate")}
              </p>
              {editing ? (
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    inputMode="decimal"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    className="w-32 rounded border border-slate-300 px-2 py-1 tabular-nums"
                  />
                  <button
                    type="button"
                    onClick={() => void save()}
                    disabled={updateMut.isPending}
                    className="rounded bg-slate-900 px-2 py-1 text-xs text-white hover:bg-slate-700 disabled:opacity-50"
                  >
                    {t("projects.budget.save")}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(false);
                      setDraft(estimate != null ? String(estimate) : "");
                    }}
                    className="rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-100"
                  >
                    {t("projects.budget.cancel")}
                  </button>
                </div>
              ) : (
                <div className="flex items-baseline gap-2">
                  <p className="text-2xl font-semibold tabular-nums">
                    {formatChf(estimate ?? 0)}
                  </p>
                  <button
                    type="button"
                    onClick={() => setEditing(true)}
                    className="text-xs text-slate-500 hover:text-slate-900"
                  >
                    {t("projects.budget.edit")}
                  </button>
                </div>
              )}
            </div>

            <div>
              <p className="text-xs text-slate-500">
                {t("projects.budget.planned")}
              </p>
              <p className="text-2xl font-semibold tabular-nums">
                {formatChf(plannedTotal)}
              </p>
            </div>

            <div>
              <p className="text-xs text-slate-500">
                {t("projects.budget.diff")}
              </p>
              <p
                data-testid="budget-diff"
                className={
                  "text-2xl font-semibold tabular-nums " +
                  (diff == null
                    ? "text-slate-400"
                    : over
                      ? "text-red-700"
                      : "text-emerald-700")
                }
              >
                {diff == null
                  ? "—"
                  : (over ? "+" : "") + formatChf(diff)}
              </p>
            </div>
          </div>

          {estimate != null && estimate > 0 && (
            <div className="mt-4">
              <div className="h-2 w-full overflow-hidden rounded bg-slate-100">
                <div
                  className={
                    "h-full " +
                    (percent != null && percent > 100
                      ? "bg-red-500"
                      : "bg-emerald-500")
                  }
                  style={{
                    width: `${Math.min(percent ?? 0, 150)}%`,
                  }}
                />
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {t("projects.budget.percentOfEstimate", { percent })}
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
```

> Note: `formatChf` lives in `@/features/costs/types` (already used by `ProjectDetailPage`). It accepts a number-like value and returns a CHF-formatted string.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/projects/BudgetCard.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/projects/BudgetCard.tsx frontend/tests/projects/BudgetCard.test.tsx
git commit -m "feat(projects): BudgetCard with inline estimate edit + variance"
```

---

## Task 5: Frontend — `LinkExistingItemsDialog`

**Files:**
- Create: `frontend/src/features/projects/LinkExistingItemsDialog.tsx`
- Create: `frontend/tests/projects/LinkExistingItemsDialog.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/projects/LinkExistingItemsDialog.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n";

vi.mock("@/api/costs", async () => {
  return {
    useCostItems: vi.fn(),
    useUpdateCostItem: vi.fn(),
  };
});

import { useCostItems, useUpdateCostItem } from "@/api/costs";
import { LinkExistingItemsDialog } from "@/features/projects/LinkExistingItemsDialog";

function withProviders(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>{ui}</I18nextProvider>
    </QueryClientProvider>
  );
}

const items = [
  { id: "c1", title: "Boden Bad", project_id: null },
  { id: "c2", title: "Sanitär Bad", project_id: null },
];

beforeEach(() => {
  (useCostItems as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    data: items,
    isLoading: false,
    isError: false,
  });
});

describe("LinkExistingItemsDialog", () => {
  it("lists unassigned items only (via filter)", () => {
    const mutateAsync = vi.fn().mockResolvedValue({});
    (useUpdateCostItem as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync,
      isPending: false,
    });
    render(
      withProviders(
        <LinkExistingItemsDialog
          objectId="o1"
          projectId="p1"
          onClose={vi.fn()}
          onLinked={vi.fn()}
        />,
      ),
    );
    expect(screen.getByText("Boden Bad")).toBeInTheDocument();
    expect(screen.getByText("Sanitär Bad")).toBeInTheDocument();
    // The hook was called with project_id_is_null
    const callArgs = (useCostItems as unknown as ReturnType<typeof vi.fn>).mock
      .calls[0];
    expect(callArgs[0]).toBe("o1");
    expect(callArgs[1]).toMatchObject({ project_id_is_null: true });
  });

  it("links selected items on confirm", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({});
    (useUpdateCostItem as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      mutateAsync,
      isPending: false,
    });
    const onLinked = vi.fn();
    render(
      withProviders(
        <LinkExistingItemsDialog
          objectId="o1"
          projectId="p1"
          onClose={vi.fn()}
          onLinked={onLinked}
        />,
      ),
    );
    fireEvent.click(screen.getByLabelText("Boden Bad"));
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfen/i }));
    await waitFor(() => expect(onLinked).toHaveBeenCalled());
    expect(mutateAsync).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/projects/LinkExistingItemsDialog.test.tsx`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `LinkExistingItemsDialog.tsx`**

Create `frontend/src/features/projects/LinkExistingItemsDialog.tsx`:

```typescript
import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useCostItems, useUpdateCostItem } from "@/api/costs";

export interface LinkExistingItemsDialogProps {
  objectId: string;
  projectId: string;
  onClose: () => void;
  onLinked: () => void;
}

export function LinkExistingItemsDialog({
  objectId,
  projectId,
  onClose,
  onLinked,
}: LinkExistingItemsDialogProps): JSX.Element {
  const { t } = useTranslation();
  const itemsQuery = useCostItems(objectId, { project_id_is_null: true });
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [submitting, setSubmitting] = useState(false);

  // We need one mutation per item; using a single hook per row would
  // need a stable id. Instead we call the lower-level updateCostItem
  // via a per-row hook factory. To keep things simple here, we call a
  // single mutation function per submit click using ad-hoc hooks for
  // each selected id.
  const updateMutFactory = (costItemId: string) =>
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useUpdateCostItem(objectId, costItemId);

  const items = itemsQuery.data ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) => i.title.toLowerCase().includes(q));
  }, [items, search]);

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const handleConfirm = async () => {
    if (selected.size === 0) return;
    setSubmitting(true);
    try {
      const ids = Array.from(selected);
      // Call updateCostItem sequentially — small N (a few items) so
      // serial is fine and keeps cache invalidation predictable.
      for (const id of ids) {
        const target = items.find((i) => i.id === id);
        if (!target) continue;
        // Build a minimal payload that only changes project_id; the
        // backend PUT requires the full shape so we round-trip the
        // existing fields.
        await updateMutFactory(id).mutateAsync({
          ...target,
          project_id: projectId,
        } as unknown as Parameters<
          ReturnType<typeof useUpdateCostItem>["mutateAsync"]
        >[0]);
      }
      onLinked();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/40 p-4"
    >
      <div className="w-full max-w-md rounded-lg bg-white p-4 shadow-lg">
        <h3 className="mb-3 text-lg font-medium">
          {t("projects.costItems.linkDialog.title")}
        </h3>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("projects.costItems.linkDialog.search")}
          className="mb-3 w-full rounded border border-slate-300 px-2 py-1 text-sm"
        />
        <div className="max-h-64 overflow-y-auto rounded border border-slate-200">
          {itemsQuery.isLoading && (
            <p className="p-3 text-sm text-slate-500">{t("common.loading")}</p>
          )}
          {!itemsQuery.isLoading && filtered.length === 0 && (
            <p className="p-3 text-sm text-slate-500">
              {t("projects.costItems.linkDialog.empty")}
            </p>
          )}
          {filtered.map((i) => (
            <label
              key={i.id}
              className="flex cursor-pointer items-center gap-2 border-b border-slate-100 px-3 py-2 text-sm last:border-b-0 hover:bg-slate-50"
            >
              <input
                type="checkbox"
                aria-label={i.title}
                checked={selected.has(i.id)}
                onChange={() => toggle(i.id)}
              />
              <span>{i.title}</span>
            </label>
          ))}
        </div>
        <div className="mt-3 flex items-center justify-between">
          <span className="text-xs text-slate-500">
            {t("projects.costItems.linkDialog.selected", { count: selected.size })}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
            >
              {t("projects.costItems.linkDialog.cancel")}
            </button>
            <button
              type="button"
              onClick={() => void handleConfirm()}
              disabled={selected.size === 0 || submitting}
              className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {t("projects.costItems.linkDialog.confirm")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

> Important caveat: calling a hook inside `handleConfirm` (via `updateMutFactory`) violates the Rules of Hooks. The lint-disable above is a temporary smell — we replace it in the next step with a stable approach.

- [ ] **Step 4: Replace hook-in-callback with the raw `updateCostItem` function**

The hook-factory approach is unsafe. Replace its usage with the underlying `updateCostItem` function (which doesn't require a hook):

In `LinkExistingItemsDialog.tsx`, change the import to:

```typescript
import { useCostItems, updateCostItem } from "@/api/costs";
import { useQueryClient } from "@tanstack/react-query";
```

Remove the `updateMutFactory` definition. In the component body add:

```typescript
const qc = useQueryClient();
```

Rewrite `handleConfirm`:

```typescript
  const handleConfirm = async () => {
    if (selected.size === 0) return;
    setSubmitting(true);
    try {
      const ids = Array.from(selected);
      for (const id of ids) {
        const target = items.find((i) => i.id === id);
        if (!target) continue;
        await updateCostItem(objectId, id, {
          ...target,
          project_id: projectId,
        } as unknown as Parameters<typeof updateCostItem>[2]);
      }
      void qc.invalidateQueries({ queryKey: ["cost-items", objectId] });
      onLinked();
    } finally {
      setSubmitting(false);
    }
  };
```

Update the test mock at the top of `LinkExistingItemsDialog.test.tsx` to mock `updateCostItem` instead of `useUpdateCostItem`:

```typescript
vi.mock("@/api/costs", async () => {
  return {
    useCostItems: vi.fn(),
    updateCostItem: vi.fn().mockResolvedValue({}),
  };
});

import { useCostItems, updateCostItem } from "@/api/costs";
```

And update the test assertions: replace every `(useUpdateCostItem as ...).mockReturnValue(...)` block with nothing (the module-level mock is enough). Change the "links selected items" test's mutate assertion to:

```typescript
    expect(updateCostItem).toHaveBeenCalledTimes(1);
```

- [ ] **Step 5: Run tests**

Run: `cd frontend && npx vitest run tests/projects/LinkExistingItemsDialog.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/projects/LinkExistingItemsDialog.tsx frontend/tests/projects/LinkExistingItemsDialog.test.tsx
git commit -m "feat(projects): link-existing-items dialog for project page"
```

---

## Task 6: Frontend — `ProjectCostItemsSection`

**Files:**
- Create: `frontend/src/features/projects/ProjectCostItemsSection.tsx`

- [ ] **Step 1: Implement the section component**

Create `frontend/src/features/projects/ProjectCostItemsSection.tsx`:

```typescript
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Drawer } from "@/components/Drawer";
import { useCostItems, useCreateCostItem, useUpdateCostItem } from "@/api/costs";
import { formatChf } from "@/features/costs/types";
import { CostItemForm } from "@/features/costs/CostItemForm";
import type { CostItem, CostItemInput } from "@/features/costs/types";
import { assignTag } from "@/features/tags/api";
import type { Tag } from "@/features/tags/types";
import type { ObjectDetail } from "@/features/objects/types";
import { LinkExistingItemsDialog } from "./LinkExistingItemsDialog";

export interface ProjectCostItemsSectionProps {
  objectId: string;
  projectId: string;
  object: ObjectDetail;
  /** Called when items change so the parent can refresh the planned-total. */
  onItemsChanged?: (() => void) | undefined;
}

export function ProjectCostItemsSection({
  objectId,
  projectId,
  object,
  onItemsChanged,
}: ProjectCostItemsSectionProps): JSX.Element {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const itemsQuery = useCostItems(objectId, { project_id: projectId });
  const items = itemsQuery.data ?? [];

  const [creating, setCreating] = useState(false);
  const [linking, setLinking] = useState(false);

  const createMut = useCreateCostItem(objectId);

  const handleCreate = async (
    payload: CostItemInput,
    pendingTags: Tag[],
  ) => {
    const created = await createMut.mutateAsync({
      ...payload,
      project_id: projectId,
    });
    for (const tag of pendingTags) {
      await assignTag("cost_item", created.id, tag.id);
    }
    setCreating(false);
    onItemsChanged?.();
  };

  // Per-row unlink. We use the raw API (not hook-per-row) to avoid Rules of Hooks issues.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const _ = useUpdateCostItem;

  const handleUnlink = async (item: CostItem) => {
    if (!window.confirm(t("projects.costItems.removeConfirm"))) return;
    const { updateCostItem } = await import("@/api/costs");
    await updateCostItem(objectId, item.id, {
      ...(item as unknown as CostItemInput),
      project_id: null,
    });
    onItemsChanged?.();
  };

  return (
    <section className="mb-8">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-lg font-medium">{t("projects.costItems.title")}</h3>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setLinking(true)}
            className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
          >
            {t("projects.costItems.link")}
          </button>
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
          >
            {t("projects.costItems.add")}
          </button>
        </div>
      </div>

      {itemsQuery.isLoading && (
        <p className="text-slate-500">{t("common.loading")}</p>
      )}
      {!itemsQuery.isLoading && items.length === 0 && (
        <p className="text-slate-500">{t("projects.costItems.empty")}</p>
      )}
      {items.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
              <th className="px-2 py-2">{t("costs.fields.title")}</th>
              <th className="px-2 py-2">{t("costs.fields.bkp")}</th>
              <th className="px-2 py-2 text-right">
                {t("costs.fields.plannedAmount")}
              </th>
              <th className="px-2 py-2" />
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b border-slate-200">
                <td
                  className="cursor-pointer px-2 py-2 font-medium hover:underline"
                  onClick={() =>
                    navigate(`/objekte/${objectId}/kosten?edit=${item.id}`)
                  }
                >
                  {item.title}
                </td>
                <td className="px-2 py-2 font-mono text-xs">
                  {item.bkp_code ?? t("costs.uncategorised")}
                </td>
                <td className="px-2 py-2 text-right tabular-nums">
                  {formatChf(item.planned_amount_chf)}
                </td>
                <td className="px-2 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => void handleUnlink(item)}
                    className="text-xs text-slate-500 hover:text-red-700"
                  >
                    {t("projects.costItems.remove")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {creating && (
        <Drawer
          title={t("projects.costItems.add")}
          onClose={() => setCreating(false)}
        >
          <CostItemForm
            units={object.units}
            objectId={objectId}
            initial={{ project_id: projectId }}
            onSubmit={handleCreate}
            onCancel={() => setCreating(false)}
            submitting={createMut.isPending}
          />
        </Drawer>
      )}

      {linking && (
        <LinkExistingItemsDialog
          objectId={objectId}
          projectId={projectId}
          onClose={() => setLinking(false)}
          onLinked={() => {
            setLinking(false);
            onItemsChanged?.();
          }}
        />
      )}
    </section>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors. If `formatChf` doesn't accept a nullable amount, check the existing `ProjectDetailPage` call site (line 137) — it currently passes `item.planned_amount_chf` which is the same shape, so this should match.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/projects/ProjectCostItemsSection.tsx
git commit -m "feat(projects): cost-items section with add + link + unlink actions"
```

---

## Task 7: Frontend — rewrite `ProjectDetailPage` to compose new sections

**Files:**
- Modify: `frontend/src/features/projects/ProjectDetailPage.tsx` (full rewrite)

- [ ] **Step 1: Rewrite the file**

Replace the entire contents of `frontend/src/features/projects/ProjectDetailPage.tsx` with:

```typescript
/**
 * Project detail page composed from a budget card, a cost-items
 * section, and a collapsible details panel (existing ProjectForm).
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { useCostItems } from "@/api/costs";
import { getObject } from "@/features/objects/api";
import type { ObjectDetail } from "@/features/objects/types";
import { apiErrorMessage } from "@/lib/apiError";
import { useTagsForTarget } from "@/features/tags/api";
import { TagChip } from "@/components/TagChip";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { ProjectForm } from "./ProjectForm";
import { BudgetCard } from "./BudgetCard";
import { ProjectCostItemsSection } from "./ProjectCostItemsSection";
import {
  useArchiveProject,
  useDeleteProject,
  useProject,
  useUpdateProject,
} from "./api";
import type { ProjectCreate } from "./types";

function sumPlanned(items: Array<{ planned_amount_chf: string | null }>): number {
  let total = 0;
  for (const i of items) {
    if (i.planned_amount_chf == null) continue;
    const n = Number(i.planned_amount_chf);
    if (Number.isFinite(n)) total += n;
  }
  return total;
}

export function ProjectDetailPage(): JSX.Element {
  const { t } = useTranslation();
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [object, setObject] = useState<ObjectDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const projectQuery = useProject(projectId ?? "");
  const updateMut = useUpdateProject(projectId ?? "");
  const archiveMut = useArchiveProject(projectId ?? "");
  const objectId = projectQuery.data?.object_id ?? "";
  const deleteMut = useDeleteProject(projectId ?? "", objectId);
  const costItemsQuery = useCostItems(objectId, { project_id: projectId });
  const tagsQuery = useTagsForTarget("project", projectId ?? "");

  useEffect(() => {
    if (!objectId) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await getObject(objectId);
        if (!cancelled) setObject(data);
      } catch (e) {
        if (!cancelled) setLoadError(apiErrorMessage(e, t("common.error")));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [objectId, t]);

  if (projectQuery.isLoading || !projectId) {
    return (
      <PageContainer width="narrow">
        <p className="text-slate-500">{t("common.loading")}</p>
      </PageContainer>
    );
  }
  if (projectQuery.isError || !projectQuery.data) {
    return (
      <PageContainer width="narrow">
        <p className="text-red-700">{t("common.error")}</p>
      </PageContainer>
    );
  }
  if (loadError) {
    return (
      <PageContainer width="narrow">
        <p className="text-red-700">{loadError}</p>
      </PageContainer>
    );
  }

  const project = projectQuery.data;
  const items = costItemsQuery.data ?? [];
  const tags = tagsQuery.data ?? [];
  const plannedTotal = sumPlanned(items);

  const handleSubmit = async (payload: ProjectCreate) => {
    await updateMut.mutateAsync(payload);
  };

  const handleArchive = async () => {
    if (!window.confirm(t("projects.archiveConfirm"))) return;
    await archiveMut.mutateAsync();
  };

  const handleDelete = async () => {
    if (!window.confirm(t("projects.deleteConfirm"))) return;
    await deleteMut.mutateAsync();
    navigate(`/objekte/${project.object_id}`);
  };

  return (
    <PageContainer width="narrow">
      <PageHeader
        title={project.name}
        subtitle={
          <>
            {t(`projects.status.${project.status}`)}
            {project.planned_year && ` · ${project.planned_year}`}
            {project.archived_at && ` · ${t("projects.archived")}`}
          </>
        }
      />

      {tags.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-1">
          {tags.map((tag) => (
            <TagChip key={tag.id} tag={tag} />
          ))}
        </div>
      )}

      <BudgetCard project={project} plannedTotal={plannedTotal} />

      {object && (
        <ProjectCostItemsSection
          objectId={objectId}
          projectId={projectId}
          object={object}
        />
      )}

      <section className="mb-8 border-t border-slate-200 pt-4">
        <button
          type="button"
          onClick={() => setDetailsOpen((v) => !v)}
          className="mb-3 text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          {detailsOpen
            ? t("projects.details.hide")
            : t("projects.details.show")}
        </button>
        {detailsOpen && (
          <ProjectForm
            initial={{
              name: project.name,
              description: project.description,
              status: project.status,
              planned_year: project.planned_year,
              rough_estimate_chf: project.rough_estimate_chf,
            }}
            onSubmit={handleSubmit}
            submitting={updateMut.isPending}
          />
        )}
      </section>

      <section className="border-t border-slate-200 pt-4">
        <div className="flex gap-2">
          {!project.archived_at && (
            <button
              type="button"
              onClick={() => void handleArchive()}
              className="rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100"
            >
              {t("projects.archive")}
            </button>
          )}
          <button
            type="button"
            onClick={() => void handleDelete()}
            className="rounded border border-red-300 px-3 py-1 text-sm text-red-700 hover:bg-red-50"
          >
            {t("projects.delete")}
          </button>
        </div>
      </section>
    </PageContainer>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Update existing test if it imports the section**

If `frontend/tests/projects/ProjectDetailPage.test.tsx` exists and previously asserted on the inline cost-items table or edit form being visible, update it to:

- Use `getObject` mock (the page now fetches the object eagerly).
- Expect the Grobschätzung text or `BudgetCard` heading (`Budget`) to be in the document.
- Expect the cost-items section heading.

If the test file does not exist or only renders smoke, leave it; Task 8 adds dedicated coverage.

Run: `cd frontend && npx vitest run tests/projects/`
Expected: PASS (or update tests minimally to match the new shape).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/projects/ProjectDetailPage.tsx frontend/tests/projects/ProjectDetailPage.test.tsx
git commit -m "feat(projects): compose detail page from BudgetCard + items section"
```

---

## Task 8: Manual verification (walk the maturity ladder)

**Files:** none (manual)

- [ ] **Step 1: Start the dev stack**

Run: `docker compose up -d` (or whichever command the README uses). Then `cd frontend && npm run dev` if the frontend isn't auto-served.

- [ ] **Step 2: Verify empty-estimate state**

Open `http://127.0.0.1:8080/projekte/<a project id>`.
Expected:
- "Budget" heading visible.
- "Keine Grobschätzung erfasst" message and a "Grobschätzung hinzufügen" button.
- "Kostenpositionen in diesem Projekt" heading with "Neue Position" and "Bestehende Position verknüpfen" buttons.

- [ ] **Step 3: Add Grobschätzung**

Click "Grobschätzung hinzufügen", enter `80000`, click Speichern.
Expected: card flips to show CHF 80'000, planned total CHF 0, Differenz -80'000 in green, bar at 0 %.

- [ ] **Step 4: Add a new position**

Click "Neue Position". In the drawer, fill title `Boden Bad`, planned amount `40000`, click Save.
Expected: drawer closes; table shows the row; planned total updates to CHF 40'000; bar 50 %.

- [ ] **Step 5: Link an existing position**

Pre-condition: at least one cost item on the same object with no project. From the project page, click "Bestehende Position verknüpfen". Select an item, click Verknüpfen.
Expected: dialog closes; table includes the newly linked item; planned total updates.

- [ ] **Step 6: Push over budget**

Edit one of the items (via the existing /kosten page) so total exceeds 80'000.
Expected: Differenz turns red with a `+` sign; bar fills past 100 % and turns red.

- [ ] **Step 7: Toggle Details**

Click "Details anzeigen".
Expected: the existing ProjectForm appears with all fields populated, including Grobschätzung as a fallback edit path. Editing here also updates the budget card.

- [ ] **Step 8: Unlink a position**

In the table, click "Von Projekt entfernen" on a row. Confirm.
Expected: row disappears; planned total drops accordingly; the unlinked item now appears again in the link dialog.

---

## Self-review

- **Spec coverage:**
  - Header — kept in `ProjectDetailPage` (PageHeader unchanged). ✓
  - Budget card with inline edit + bar + diff — Task 4. ✓
  - Kostenpositionen section with create + link buttons, picker scoped to unassigned — Tasks 5, 6. ✓
  - Picker scoped to **only unassigned** items via `project_id_is_null` filter — Tasks 1, 2, 5. ✓
  - Collapsible Details wrapping the existing form — Task 7. ✓
  - Danger zone (archive, delete) — kept in Task 7. ✓
  - i18n keys — Task 3. ✓
  - Backend `project_id_is_null` filter — Task 1. ✓
  - Cost-item PATCH already supports `project_id`; no change needed beyond existing `updateCostItem`. ✓
  - Tests for backend filter (Task 1), BudgetCard (Task 4), LinkDialog (Task 5). ✓
  - Manual walkthrough — Task 8. ✓

- **Out of scope from spec is also out of scope in plan:** quote/Offerte UI, lot/Vergabe assignment, multi-project hierarchies, expert-cost templates. ✓

- **Type consistency check:**
  - `project_id_is_null` used identically in `CostItemFilter` (backend), `CostItemFilters` (frontend), `filtersToQuery`, and `LinkExistingItemsDialog`. ✓
  - `BudgetCardProps`, `LinkExistingItemsDialogProps`, `ProjectCostItemsSectionProps` all consistent across creation and import sites. ✓
  - `updateCostItem(objectId, costItemId, payload)` signature matches existing `frontend/src/api/costs.ts:79-93`. ✓
