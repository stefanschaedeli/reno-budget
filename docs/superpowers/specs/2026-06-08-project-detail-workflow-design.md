# Project detail page — workflow-driven rework

Date: 2026-06-08
Status: Draft (awaiting user review)

## Problem

Today `ProjectDetailPage` shows project metadata in a single edit form, plus a read-only list of cost items linked to the project. Two concrete issues raised by the user:

1. **The Grobschätzung (rough estimate) field is not visible in the GUI.** It exists in `ProjectForm.tsx` (line 139-156) and renders only inside the edit form section — users navigating to a project see no clear "set the budget" affordance.
2. **There is no way to add cost items to a project from the project page.** Items can be linked via `project_id` server-side, but the GUI offers neither *create-and-link* nor *link-existing*.

## User workflow this page must support

Renovation work matures in stages. The page must let the user start with zero detail and add structure as it becomes available:

```
Idee → Grobschätzung → Kostenplanung → Offerten → Vergabe
```

- **Idee:** name, status, description. No numbers.
- **Grobschätzung:** a single CHF estimate, often from an expert/architect, with optional note.
- **Kostenplanung:** detailed line items (eBKP-H coded), each with a planned amount.
- **Offerten / Vergabe:** quote and award tracking happen on cost-item detail pages (already implemented elsewhere) — this page only *surfaces* their state.

## Design

### Page layout (top to bottom)

1. **Header** — project name, status badge, planned year, tags. (Already exists; keep.)
2. **Budget card** (new, always visible)
3. **Kostenpositionen section** (new layout: table + add buttons)
4. **Details** (collapsible, contains today's `ProjectForm`)
5. **Danger zone** — archive, delete. (Already exists; keep at bottom.)

### Budget card

A three-column compact card surfacing the budget state at a glance.

```
┌───────────────────────────────────────────────────────────────┐
│  Grobschätzung            Geplant aus Positionen      Differenz│
│  CHF 80'000  [edit]       CHF 83'200                  +3'200   │
│  [───────────────────────────████]   104 %                      │
└───────────────────────────────────────────────────────────────┘
```

- **Grobschätzung** — current `rough_estimate_chf`, big, tabular-nums. Click pencil → inline number input + save/cancel. PATCHes `rough_estimate_chf` only.
- **Geplant aus Positionen** — sum of `planned_amount_chf` across this project's cost items.
- **Differenz** — `geplant − grobschätzung`. Red if positive (over), green if non-positive (at/under). Show `—` when `rough_estimate_chf` is null.
- **Bar** — fills toward 100 % of Grobschätzung; turns red past 100 %. Hidden when `rough_estimate_chf` is null or zero. Percent label to the right of the bar.

When `rough_estimate_chf` is null, the card shows a single-button empty state: **"Grobschätzung hinzufügen"** opening the same inline editor. Other columns render `—`.

### Kostenpositionen section

Heading row with two buttons:

- **+ Neue Position** — opens the existing `CostItemForm` modal/dialog pre-populated with `project_id = <this project>` and `object_id = <project.object_id>`. On submit, refetch the project's items and the budget sum.
- **Bestehende Position verknüpfen** — opens a picker dialog listing **only cost items on the same object that have no `project_id`** (a.k.a. unassigned). Multi-select. Confirming the selection PATCHes each chosen item to set `project_id`. The picker dialog has its own search/filter input on `title`.

Table beneath: today's columns (Title, BKP, Geplant) plus:
- An **Angebot** column showing the current best quote per item (if any). Sourced from existing quote API; falls back to `—`.
- A row-level **action menu** (kebab) with: *Bearbeiten* (existing cost-item detail page), *Von Projekt entfernen* (PATCH `project_id=null`).
- Empty state: "Noch keine Positionen. Beginnen Sie mit *Neue Position* oder verknüpfen Sie bestehende."

### Details (collapsible)

Wraps the existing `ProjectForm`. Collapsed by default. Holds: name, description, status, planned_year, **and** `rough_estimate_chf` (kept here too as a fallback edit path). Single "Bearbeiten" toggle button at the section header.

Reason for keeping rough_estimate_chf in two places: the budget card is the primary entry, but bulk-editing all metadata at once (e.g. when archiving / renaming) is faster in the form.

## Backend changes

The cost-item filter already supports `project_id`. We need one addition:

- **Unassigned filter:** add `project_id_is_null: bool` to `CostItemFilter` (`backend/app/schemas/cost.py`). When `true`, return only items with `project_id IS NULL` on the given object. Mutually exclusive with `project_id` (reject with 400 if both set).

Rationale: the picker dialog needs to list *unassigned items on this object*. A sentinel value on the existing `project_id` query param (e.g. `none`) is less clean than a boolean, and a dedicated `/cost-items/unassigned` endpoint is overkill.

No other backend changes — `PATCH /cost-items/{id}` already accepts `project_id` updates.

## Frontend changes

New / changed files:

- `frontend/src/features/projects/BudgetCard.tsx` (new) — props: `{ project, plannedTotal }`. Owns inline edit state and calls `useUpdateProject`.
- `frontend/src/features/projects/ProjectCostItemsSection.tsx` (new) — owns the table + both buttons. Triggers the two dialogs.
- `frontend/src/features/projects/LinkExistingItemsDialog.tsx` (new) — picker dialog.
- `frontend/src/features/projects/ProjectDetailPage.tsx` (changed) — composes the new sections; collapses the existing form.
- `frontend/src/api/costs.ts` (changed) — add `project_id_is_null` to the filter type.
- `frontend/src/features/costs/types.ts` (changed) — add `project_id_is_null` to the filter Zod schema.
- `frontend/src/i18n/locales/de.ts` (changed) — new keys: `projects.budget.heading`, `projects.budget.estimate`, `projects.budget.planned`, `projects.budget.diff`, `projects.budget.addEstimate`, `projects.budget.over`, `projects.budget.under`, `projects.costItems.add`, `projects.costItems.link`, `projects.costItems.linkDialog.*`, `projects.costItems.remove`, `projects.details.heading`, `projects.details.toggle`.

The existing `CostItemForm` is reused as-is for "Neue Position" — invoked with `project_id` and `object_id` pre-set.

## Data flow

- `useProject(projectId)` — unchanged.
- `useCostItems(objectId, { project_id: projectId })` — unchanged; used by the table.
- `useCostItems(objectId, { project_id_is_null: true })` — new use, by the picker dialog.
- Planned-total sum: derived client-side from the items query result.
- Mutations: `useUpdateProject` for inline Grobschätzung edit; `useCreateCostItem` for "Neue Position"; per-item `useUpdateCostItem` to set/clear `project_id`.

After any mutation that changes the items belonging to this project, invalidate both `cost-items` (object scope) and the project query.

## Testing

Unit / integration:

- Backend: `project_id_is_null` filter returns only unassigned items; rejects when combined with `project_id`.
- Frontend (`ProjectDetailPage.test.tsx`):
  - Renders Grobschätzung empty state when `rough_estimate_chf` is null.
  - Inline edit submits a PATCH with only the estimate field.
  - Planned total reflects the sum of fetched cost items.
  - "Neue Position" opens dialog with `project_id` pre-set.
  - "Verknüpfen" lists only unassigned items and PATCHes selected ones on confirm.
  - Removing an item from the project clears `project_id` and removes it from the table.

Manual:

- Walk the maturity ladder: create empty project → add Grobschätzung → add two positions → link one existing → check sums + variance bar at 50 %, 100 %, 120 %.

## Out of scope

- Quote/Offerte capture UI (already exists on cost-item detail).
- Lot/Vergabe assignment (exists in lots feature).
- Multi-project hierarchies / phases — keep flat for now.
- Expert-cost-guidance templates ("Architekt schlägt für Bad 80k vor") — future feature; the current free-text description suffices.
