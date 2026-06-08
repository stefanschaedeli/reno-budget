# Cross-Object Lists (PR 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add cross-object top-level list pages for Projects / Lots / Suppliers — one row per resource across every object the user has access to — and normalize the frontend `/projects/:id` detail route to `/projekte/:id` for consistency with the already-German `/lose/:id` and `/lieferanten/:id`.

**Architecture:** Backend adds three new `GET /api/v1/projects | /lots | /suppliers` endpoints. Each follows the existing `GET /api/v1/finances/overview` pattern: enumerate the user's objects via `list_objects_for_user`, then per-object call the existing service (`list_projects` etc.). Response items carry parent `object_id` + `object_name` (new field) so the UI can show the parent without a second request. Three new list page components consume these endpoints. The orphan English route `/projects/:id` is renamed to `/projekte/:id` in `App.tsx`, the single `<Link>` consumer, the `AppLayout` breadcrumb match, and the regex in `DETAIL_ID_PATTERNS`. Backend `/api/v1/projects/{id}` API path stays English — backend RESTful resource paths are not localized.

**Tech Stack:** FastAPI + SQLAlchemy async + Pydantic v2 (backend); React 18 + TanStack Query + react-router-dom + Tailwind + i18next (frontend).

---

## Out of scope

- Cross-object archived toggle (we hide archived by default; no UI toggle in this PR — YAGNI until requested)
- Search / filter on the new lists (YAGNI)
- Pagination — current dataset sizes are tiny, follow the existing per-object list pattern of "return all"
- Renaming the backend `/api/v1/projects/{id}` REST path (keep English on the API surface)

---

## File Structure

**Backend — Created:**
- `backend/tests/integration/test_cross_object_lists.py` — pytest covering visibility (only owns), excludes-archived-by-default, sort order, empty case

**Backend — Modified:**
- `backend/app/schemas/project.py` — add `ProjectListItem(ProjectRead)` with extra `object_name: str`
- `backend/app/schemas/lot.py` — add `LotListItem(LotRead)` with extra `object_name: str`
- `backend/app/schemas/supplier.py` — add `SupplierListItem(SupplierRead)` with extra `object_name: str`
- `backend/app/api/v1/projects.py` — add `GET /` on `router_projects`
- `backend/app/api/v1/lots.py` — add `GET /` on `router_lots`
- `backend/app/api/v1/suppliers.py` — add `GET /` on `router_suppliers`

**Frontend — Created:**
- `frontend/src/features/projects/AllProjectsPage.tsx` — cross-object list page
- `frontend/src/features/lots/AllLotsPage.tsx`
- `frontend/src/features/suppliers/AllSuppliersPage.tsx`

**Frontend — Modified:**
- `frontend/src/features/projects/api.ts` — add `useAllProjects` hook
- `frontend/src/features/lots/api.ts` — add `useAllLots`
- `frontend/src/features/suppliers/api.ts` — add `useAllSuppliers`
- `frontend/src/features/projects/types.ts` — add `ProjectListItem = Project & { object_name: string }`
- `frontend/src/features/lots/types.ts` — same shape
- `frontend/src/features/suppliers/types.ts` — same shape
- `frontend/src/app/App.tsx` — add three new authenticated routes (`/projekte`, `/lose-uebersicht`, `/lieferanten-uebersicht`) + rename `/projects/:projectId` → `/projekte/:projectId`

  ⚠ **Route naming caveat:** `/objekte/:objectId/projekte` already exists (per-object project list). To avoid collision, the cross-object top-level pages use distinct paths:
  - Projects cross-list: `/projekte` (top-level, no slug — distinguishable from `/objekte/:id/projekte` because that one has the `objekte/<id>/` prefix)
  - Lots cross-list: `/lose` is already taken by `LotDetailPage` (`/lose/:lotId`). Use `/lose-uebersicht` to avoid ambiguity.
  - Suppliers cross-list: `/lieferanten` is already taken by `SupplierDetailPage` (`/lieferanten/:supplierId`). Use `/lieferanten-uebersicht`.
  - Project detail: `/projekte/:projectId` (renamed from `/projects/:projectId`) — note path collision with `/projekte` top-level list. react-router-dom v6 resolves exact paths before parametric, so `/projekte` (no slug) → list, `/projekte/<uuid>` → detail. **This is safe** but the test plan must verify.
- `frontend/src/features/projects/ProjectsPage.tsx` — update the inline `<Link to="/projects/${p.id}">` to `/projekte/${p.id}`
- `frontend/src/components/AppLayout.tsx`:
  - Update `DETAIL_ID_PATTERNS.projects` regex from `/^\/projects\//` to `/^\/projekte\/(?!$)/` (the `(?!$)` prevents matching the bare `/projekte` cross-object list)
  - Update `useBreadcrumbs` branch from `parts[0] === "projects"` to `parts[0] === "projekte" && parts[1]` for detail-page handling (already partially correct since the existing branch checks `&& parts[1]`)
  - Add top-level sidebar links for Projekte / Lose / Lieferanten between Objekte and Finanzen
  - Extend `useBreadcrumbs` with new top-level branches for `/projekte`, `/lose-uebersicht`, `/lieferanten-uebersicht`
- `frontend/src/i18n/locales/de.ts` — three new top-level keys: `nav.projektsListe`, `nav.lotsListe`, `nav.suppliersListe` (top-level nav labels distinct from per-object breadcrumb labels)

---

## Task 1: Backend — `ProjectListItem` schema

**Files:**
- Modify: `backend/app/schemas/project.py`

Add a new schema that extends `ProjectRead` with `object_name`. Keep `ProjectRead` unchanged so per-object endpoints are unaffected.

- [ ] **Step 1: Add schema at the bottom of `backend/app/schemas/project.py`**

After the existing `ProjectRead` class, append:

```python
class ProjectListItem(ProjectRead):
    """ProjectRead enriched with the parent object's name.

    Used by the cross-object list endpoint at ``GET /api/v1/projects``
    where rows span multiple objects and the UI needs to render the
    parent's name without a second fetch.
    """

    object_name: str
```

- [ ] **Step 2: Run mypy / linting (project-specific)**

Run: `cd /Users/stefan/Code/reno-budget/backend && python -m ruff check app/schemas/project.py`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/project.py
git commit -m "feat(schemas): ProjectListItem for cross-object listing"
```

---

## Task 2: Backend — `LotListItem` schema

**Files:**
- Modify: `backend/app/schemas/lot.py`

- [ ] **Step 1: Add schema at the bottom of `backend/app/schemas/lot.py`**

```python
class LotListItem(LotRead):
    """LotRead enriched with the parent object's name (cross-object listing)."""

    object_name: str
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/lot.py
git commit -m "feat(schemas): LotListItem for cross-object listing"
```

---

## Task 3: Backend — `SupplierListItem` schema

**Files:**
- Modify: `backend/app/schemas/supplier.py`

- [ ] **Step 1: Add schema at the bottom of `backend/app/schemas/supplier.py`**

```python
class SupplierListItem(SupplierRead):
    """SupplierRead enriched with the parent object's name (cross-object listing)."""

    object_name: str
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/supplier.py
git commit -m "feat(schemas): SupplierListItem for cross-object listing"
```

---

## Task 4: Backend — failing test for cross-object endpoints

**Files:**
- Create: `backend/tests/integration/test_cross_object_lists.py`

Write the integration tests first (TDD). Tests must cover:
- A user sees only resources of objects they have membership on
- Resources from a different user's object are NOT visible
- Archived resources are excluded by default
- Empty case returns `[]` with 200
- Each row carries `object_id` AND `object_name`

- [ ] **Step 1: Create the test file**

```python
"""Cross-object list endpoints (PR 2).

Covers ``GET /api/v1/projects``, ``GET /api/v1/lots``, ``GET /api/v1/suppliers`` —
one row per resource across every object the calling user has access to.
"""

from __future__ import annotations

import datetime as _dt
import uuid

import pytest
import pytest_asyncio
from app.core.security import hash_password
from app.models.lot import Lot, LotStatus
from app.models.object import (
    Object,
    ObjectMembership,
    ObjectRole,
    ObjectType,
)
from app.models.project import Project, ProjectStatus
from app.models.supplier import Supplier
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

PW = "horse-battery-staple-correct-9"  # nosec B105


async def _mk_user(session: AsyncSession, email: str) -> User:
    u = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(PW),
        display_name=email.split("@")[0],
        is_active=True,
    )
    session.add(u)
    await session.commit()
    return u


async def _mk_object_with_owner(
    session: AsyncSession, owner: User, name: str
) -> Object:
    obj = Object(
        id=uuid.uuid4(),
        name=name,
        type=ObjectType.MFH,
        planning_horizon_years=30,
    )
    session.add(obj)
    session.add(
        ObjectMembership(
            user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER
        )
    )
    await session.commit()
    return obj


async def _login(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PW},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def two_users_two_objects(session: AsyncSession):
    """Owner-Alice with Object-A; Owner-Bob with Object-B."""
    alice = await _mk_user(session, "alice@example.com")
    bob = await _mk_user(session, "bob@example.com")
    obj_a = await _mk_object_with_owner(session, alice, "Haus A")
    obj_b = await _mk_object_with_owner(session, bob, "Haus B")
    return alice, bob, obj_a, obj_b


@pytest.mark.asyncio
async def test_projects_cross_list_only_my_objects(
    two_users_two_objects, session: AsyncSession, client: AsyncClient
):
    alice, bob, obj_a, obj_b = two_users_two_objects
    # Add a project to each
    p_a = Project(
        id=uuid.uuid4(),
        object_id=obj_a.id,
        name="Dach A",
        status=ProjectStatus.PLANNED,
        created_by=alice.id,
    )
    p_b = Project(
        id=uuid.uuid4(),
        object_id=obj_b.id,
        name="Dach B",
        status=ProjectStatus.PLANNED,
        created_by=bob.id,
    )
    session.add_all([p_a, p_b])
    await session.commit()

    token = await _login(client, alice.email)
    r = await client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == str(p_a.id)
    assert rows[0]["object_id"] == str(obj_a.id)
    assert rows[0]["object_name"] == "Haus A"


@pytest.mark.asyncio
async def test_projects_cross_list_excludes_archived(
    two_users_two_objects, session: AsyncSession, client: AsyncClient
):
    alice, _, obj_a, _ = two_users_two_objects
    active = Project(
        id=uuid.uuid4(),
        object_id=obj_a.id,
        name="Aktiv",
        status=ProjectStatus.PLANNED,
        created_by=alice.id,
    )
    archived = Project(
        id=uuid.uuid4(),
        object_id=obj_a.id,
        name="Archiviert",
        status=ProjectStatus.PLANNED,
        created_by=alice.id,
        archived_at=_dt.datetime.now(_dt.timezone.utc),
    )
    session.add_all([active, archived])
    await session.commit()

    token = await _login(client, alice.email)
    r = await client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    names = [row["name"] for row in r.json()]
    assert names == ["Aktiv"]


@pytest.mark.asyncio
async def test_projects_cross_list_empty(
    two_users_two_objects, client: AsyncClient
):
    alice, _, _, _ = two_users_two_objects
    token = await _login(client, alice.email)
    r = await client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_lots_cross_list_only_my_objects(
    two_users_two_objects, session: AsyncSession, client: AsyncClient
):
    alice, bob, obj_a, obj_b = two_users_two_objects
    l_a = Lot(
        id=uuid.uuid4(),
        object_id=obj_a.id,
        name="Los A",
        status=LotStatus.DRAFT,
        created_by=alice.id,
    )
    l_b = Lot(
        id=uuid.uuid4(),
        object_id=obj_b.id,
        name="Los B",
        status=LotStatus.DRAFT,
        created_by=bob.id,
    )
    session.add_all([l_a, l_b])
    await session.commit()

    token = await _login(client, alice.email)
    r = await client.get(
        "/api/v1/lots", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == str(l_a.id)
    assert rows[0]["object_name"] == "Haus A"


@pytest.mark.asyncio
async def test_suppliers_cross_list_only_my_objects(
    two_users_two_objects, session: AsyncSession, client: AsyncClient
):
    alice, bob, obj_a, obj_b = two_users_two_objects
    s_a = Supplier(
        id=uuid.uuid4(),
        object_id=obj_a.id,
        name="Firma A",
        created_by=alice.id,
    )
    s_b = Supplier(
        id=uuid.uuid4(),
        object_id=obj_b.id,
        name="Firma B",
        created_by=bob.id,
    )
    session.add_all([s_a, s_b])
    await session.commit()

    token = await _login(client, alice.email)
    r = await client.get(
        "/api/v1/suppliers", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == str(s_a.id)
    assert rows[0]["object_name"] == "Haus A"
```

- [ ] **Step 2: Verify tests FAIL (endpoints don't exist yet)**

Run: `cd /Users/stefan/Code/reno-budget/backend && pytest tests/integration/test_cross_object_lists.py -v`
Expected: all 5 tests fail with 404 (route not found) or 405 (router exists but no GET handler).

- [ ] **Step 3: Commit failing tests**

```bash
git add backend/tests/integration/test_cross_object_lists.py
git commit -m "test(cross-object): failing tests for /projects, /lots, /suppliers list"
```

> **Note on model field names:** This test uses `Project(name=..., created_by=..., status=ProjectStatus.PLANNED, ...)`. If the model insists on more required fields the test will surface them in step 2's failure mode (validation error vs 404). Add the missing fields then. Don't proceed to Task 5 until the failure is "route not found" — that means the model construction worked.

---

## Task 5: Backend — implement `GET /api/v1/projects`

**Files:**
- Modify: `backend/app/api/v1/projects.py`

Add a `GET /` handler on the existing `router_projects` that iterates the user's accessible objects and concatenates per-object `list_projects` results.

- [ ] **Step 1: Add imports at the top of `backend/app/api/v1/projects.py`**

The file currently imports `list_projects` from `app.services.projects`. Add to existing imports:

```python
from app.repositories.object import list_objects_for_user
from app.schemas.project import ProjectListItem
```

- [ ] **Step 2: Add the handler**

Add this handler to `router_projects` (it has prefix `/projects`):

```python
@router_projects.get("", response_model=list[ProjectListItem])
async def list_all_projects(
    user: CurrentUser,
    session: SessionDep,
) -> list[ProjectListItem]:
    """All non-archived projects across every object the user can access.

    Mirrors the ``/finances/overview`` pattern: enumerate the user's objects
    via ``list_objects_for_user`` (which joins through ``ObjectMembership``),
    then per object call the existing service. Archived rows are excluded.
    Sorted by object name then project created_at (matches per-object order).
    """
    objects = await list_objects_for_user(session, user.id)
    items: list[ProjectListItem] = []
    for obj in objects:
        rows = await list_projects(session, object_id=obj.id, include_archived=False)
        for p in rows:
            items.append(
                ProjectListItem.model_validate(
                    {**ProjectRead.model_validate(p).model_dump(), "object_name": obj.name}
                )
            )
    return items
```

Make sure `ProjectRead` is imported — it's already imported in this file via `from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate` at the top. If not, add it.

- [ ] **Step 3: Re-run the test**

Run: `cd /Users/stefan/Code/reno-budget/backend && pytest tests/integration/test_cross_object_lists.py::test_projects_cross_list_only_my_objects tests/integration/test_cross_object_lists.py::test_projects_cross_list_excludes_archived tests/integration/test_cross_object_lists.py::test_projects_cross_list_empty -v`
Expected: all 3 project tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/projects.py
git commit -m "feat(api): GET /projects cross-object list"
```

---

## Task 6: Backend — implement `GET /api/v1/lots`

**Files:**
- Modify: `backend/app/api/v1/lots.py`

Mirror Task 5 for lots.

- [ ] **Step 1: Add imports** to `backend/app/api/v1/lots.py`

```python
from app.repositories.object import list_objects_for_user
from app.schemas.lot import LotListItem
```

(`LotRead` is already imported; verify by grep.)

- [ ] **Step 2: Add handler to `router_lots`** (prefix `/lots`)

```python
@router_lots.get("", response_model=list[LotListItem])
async def list_all_lots(
    user: CurrentUser,
    session: SessionDep,
) -> list[LotListItem]:
    """All non-archived lots across every object the user can access."""
    objects = await list_objects_for_user(session, user.id)
    items: list[LotListItem] = []
    for obj in objects:
        rows = await list_lots(session, object_id=obj.id, include_archived=False)
        for l in rows:
            items.append(
                LotListItem.model_validate(
                    {**LotRead.model_validate(l).model_dump(), "object_name": obj.name}
                )
            )
    return items
```

- [ ] **Step 3: Re-run the test**

Run: `cd /Users/stefan/Code/reno-budget/backend && pytest tests/integration/test_cross_object_lists.py::test_lots_cross_list_only_my_objects -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/lots.py
git commit -m "feat(api): GET /lots cross-object list"
```

---

## Task 7: Backend — implement `GET /api/v1/suppliers`

**Files:**
- Modify: `backend/app/api/v1/suppliers.py`

Mirror Task 5 for suppliers.

- [ ] **Step 1: Add imports**

```python
from app.repositories.object import list_objects_for_user
from app.schemas.supplier import SupplierListItem
```

- [ ] **Step 2: Add handler to `router_suppliers`** (prefix `/suppliers`)

```python
@router_suppliers.get("", response_model=list[SupplierListItem])
async def list_all_suppliers(
    user: CurrentUser,
    session: SessionDep,
) -> list[SupplierListItem]:
    """All non-archived suppliers across every object the user can access."""
    objects = await list_objects_for_user(session, user.id)
    items: list[SupplierListItem] = []
    for obj in objects:
        rows = await list_suppliers(session, object_id=obj.id, include_archived=False)
        for s in rows:
            items.append(
                SupplierListItem.model_validate(
                    {**SupplierRead.model_validate(s).model_dump(), "object_name": obj.name}
                )
            )
    return items
```

- [ ] **Step 3: Re-run the test**

Run: `cd /Users/stefan/Code/reno-budget/backend && pytest tests/integration/test_cross_object_lists.py -v`
Expected: ALL 5 cross-object tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/suppliers.py
git commit -m "feat(api): GET /suppliers cross-object list"
```

---

## Task 8: Backend — full test suite sanity

**Files:**
- None — verification only.

- [ ] **Step 1: Run the full backend test suite**

Run: `cd /Users/stefan/Code/reno-budget/backend && pytest -x --tb=short`
Expected: all tests pass. The new endpoints shouldn't break anything because they're additive — existing per-object endpoints (`GET /objects/{id}/projects`) are untouched.

If any existing test fails, read its assertion carefully — most likely cause would be that a test was using a path that now matches a different handler (e.g. `GET /projects` previously returned 405, now returns 200 with a list). Update test expectations if so.

- [ ] **Step 2: Commit any test fixups** (probably none)

---

## Task 9: Frontend — `ProjectListItem` type

**Files:**
- Modify: `frontend/src/features/projects/types.ts`

Add a type matching the backend `ProjectListItem` schema.

- [ ] **Step 1: Append to `frontend/src/features/projects/types.ts`**

Add at the bottom of the file:

```ts
export const projectListItemSchema = projectSchema.extend({
  object_name: z.string(),
});

export type ProjectListItem = z.infer<typeof projectListItemSchema>;
```

Verify `z` is already imported (it is — the file uses zod for `projectSchema`).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/projects/types.ts
git commit -m "feat(types): ProjectListItem for cross-object list"
```

---

## Task 10: Frontend — `LotListItem` type

**Files:**
- Modify: `frontend/src/features/lots/types.ts`

- [ ] **Step 1: Append**

```ts
export const lotListItemSchema = lotSchema.extend({
  object_name: z.string(),
});

export type LotListItem = z.infer<typeof lotListItemSchema>;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/lots/types.ts
git commit -m "feat(types): LotListItem for cross-object list"
```

---

## Task 11: Frontend — `SupplierListItem` type

**Files:**
- Modify: `frontend/src/features/suppliers/types.ts`

- [ ] **Step 1: Append**

```ts
export const supplierListItemSchema = supplierSchema.extend({
  object_name: z.string(),
});

export type SupplierListItem = z.infer<typeof supplierListItemSchema>;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/suppliers/types.ts
git commit -m "feat(types): SupplierListItem for cross-object list"
```

---

## Task 12: Frontend — `useAllProjects` hook

**Files:**
- Modify: `frontend/src/features/projects/api.ts`

- [ ] **Step 1: Add the fetcher + hook to `frontend/src/features/projects/api.ts`**

After the existing `fetchProjects` / `useProjects`, add:

```ts
export async function fetchAllProjects(): Promise<ProjectListItem[]> {
  const raw = await apiRequest<unknown>(`/projects`);
  return z.array(projectListItemSchema).parse(raw);
}

export function useAllProjects(): UseQueryResult<ProjectListItem[]> {
  return useQuery({
    queryKey: ["projects-all"],
    queryFn: fetchAllProjects,
  });
}
```

Update the `projectListItemSchema` / `ProjectListItem` imports at the top:

```ts
import { type ProjectListItem, projectListItemSchema } from "./types";
```

(Add to existing import line for the types module.)

- [ ] **Step 2: Run typecheck**

Run: `cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/projects/api.ts
git commit -m "feat(api): useAllProjects hook"
```

---

## Task 13: Frontend — `useAllLots` hook

**Files:**
- Modify: `frontend/src/features/lots/api.ts`

- [ ] **Step 1: Add fetcher + hook**

```ts
export async function fetchAllLots(): Promise<LotListItem[]> {
  const raw = await apiRequest<unknown>(`/lots`);
  return z.array(lotListItemSchema).parse(raw);
}

export function useAllLots(): UseQueryResult<LotListItem[]> {
  return useQuery({
    queryKey: ["lots-all"],
    queryFn: fetchAllLots,
  });
}
```

Add the type import:

```ts
import { type LotListItem, lotListItemSchema } from "./types";
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit
git add frontend/src/features/lots/api.ts
git commit -m "feat(api): useAllLots hook"
```

---

## Task 14: Frontend — `useAllSuppliers` hook

**Files:**
- Modify: `frontend/src/features/suppliers/api.ts`

- [ ] **Step 1: Add fetcher + hook**

```ts
export async function fetchAllSuppliers(): Promise<SupplierListItem[]> {
  const raw = await apiRequest<unknown>(`/suppliers`);
  return z.array(supplierListItemSchema).parse(raw);
}

export function useAllSuppliers(): UseQueryResult<SupplierListItem[]> {
  return useQuery({
    queryKey: ["suppliers-all"],
    queryFn: fetchAllSuppliers,
  });
}
```

```ts
import { type SupplierListItem, supplierListItemSchema } from "./types";
```

- [ ] **Step 2: Typecheck + commit**

```bash
cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit
git add frontend/src/features/suppliers/api.ts
git commit -m "feat(api): useAllSuppliers hook"
```

---

## Task 15: Frontend — `AllProjectsPage` component

**Files:**
- Create: `frontend/src/features/projects/AllProjectsPage.tsx`

Mirror the `FinancesPage` shape: PageContainer/PageHeader, table with project name → detail link, parent object → object link, status column. Hide archived by default (backend already excludes them, but caller may extend with a toggle later).

- [ ] **Step 1: Create the file**

```tsx
/**
 * Cross-object project list.
 *
 * One row per non-archived project across every object the current user
 * can access. Each row links to the project's detail page and to its
 * parent object. Mirrors the FinancesPage cross-object pattern.
 */
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { useAllProjects } from "./api";
import type { ProjectListItem } from "./types";

export function AllProjectsPage(): JSX.Element {
  const { t } = useTranslation();
  const q = useAllProjects();

  return (
    <PageContainer width="default">
      <PageHeader
        title={t("projects.allTitle")}
        subtitle={t("projects.allSubtitle")}
      />

      {q.isLoading && <p className="text-slate-500">{t("common.loading")}</p>}
      {q.isError && <p className="text-red-700">{t("common.error")}</p>}
      {q.isSuccess && q.data.length === 0 && (
        <p className="text-slate-500">{t("projects.empty")}</p>
      )}
      {q.isSuccess && q.data.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
              <th className="px-2 py-2">{t("projects.fields.name")}</th>
              <th className="px-2 py-2">{t("projects.fields.object")}</th>
              <th className="px-2 py-2">{t("projects.fields.status")}</th>
              <th className="px-2 py-2">{t("projects.fields.plannedYear")}</th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((p: ProjectListItem) => (
              <tr
                key={p.id}
                data-testid={`all-project-row-${p.id}`}
                className="border-b border-slate-200 hover:bg-slate-50"
              >
                <td className="px-2 py-2 font-medium">
                  <Link to={`/projekte/${p.id}`} className="hover:underline">
                    {p.name}
                  </Link>
                </td>
                <td className="px-2 py-2">
                  <Link
                    to={`/objekte/${p.object_id}`}
                    className="text-slate-600 underline-offset-2 hover:underline"
                  >
                    {p.object_name}
                  </Link>
                </td>
                <td className="px-2 py-2">
                  {t(`projects.status.${p.status}`)}
                </td>
                <td className="px-2 py-2">{p.planned_year ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 2: Add i18n keys to `frontend/src/i18n/locales/de.ts`**

Under the existing `projects: {` namespace, add:
```ts
    allTitle: "Alle Projekte",
    allSubtitle: "Alle Projekte über alle Objekte",
    fields: {
      // ... existing fields preserved
      object: "Objekt",
    },
```

If `fields.object` already exists, leave it. Add only what's missing. The new keys are: `projects.allTitle`, `projects.allSubtitle`, and possibly `projects.fields.object`.

- [ ] **Step 3: Typecheck + commit**

```bash
cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit
git add frontend/src/features/projects/AllProjectsPage.tsx frontend/src/i18n/locales/de.ts
git commit -m "feat(projects): AllProjectsPage cross-object view"
```

---

## Task 16: Frontend — `AllLotsPage` component

**Files:**
- Create: `frontend/src/features/lots/AllLotsPage.tsx`

- [ ] **Step 1: Create the file** (mirroring AllProjectsPage)

```tsx
/**
 * Cross-object lot list.
 */
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { useAllLots } from "./api";
import type { LotListItem } from "./types";

export function AllLotsPage(): JSX.Element {
  const { t } = useTranslation();
  const q = useAllLots();

  return (
    <PageContainer width="default">
      <PageHeader title={t("lots.allTitle")} subtitle={t("lots.allSubtitle")} />

      {q.isLoading && <p className="text-slate-500">{t("common.loading")}</p>}
      {q.isError && <p className="text-red-700">{t("common.error")}</p>}
      {q.isSuccess && q.data.length === 0 && (
        <p className="text-slate-500">{t("lots.empty")}</p>
      )}
      {q.isSuccess && q.data.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
              <th className="px-2 py-2">{t("lots.fields.name")}</th>
              <th className="px-2 py-2">{t("lots.fields.object")}</th>
              <th className="px-2 py-2">{t("lots.fields.status")}</th>
              <th className="px-2 py-2">{t("lots.fields.tenderDeadline")}</th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((l: LotListItem) => (
              <tr
                key={l.id}
                data-testid={`all-lot-row-${l.id}`}
                className="border-b border-slate-200 hover:bg-slate-50"
              >
                <td className="px-2 py-2 font-medium">
                  <Link to={`/lose/${l.id}`} className="hover:underline">
                    {l.name}
                  </Link>
                </td>
                <td className="px-2 py-2">
                  <Link
                    to={`/objekte/${l.object_id}`}
                    className="text-slate-600 underline-offset-2 hover:underline"
                  >
                    {l.object_name}
                  </Link>
                </td>
                <td className="px-2 py-2">{t(`lots.status.${l.status}`)}</td>
                <td className="px-2 py-2">
                  {l.tender_deadline
                    ? new Date(l.tender_deadline).toLocaleDateString("de-CH")
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 2: Add i18n keys** to `de.ts` under `lots: {`:

```ts
    allTitle: "Alle Lose",
    allSubtitle: "Alle Lose über alle Objekte",
    fields: {
      // ... existing
      object: "Objekt",
    },
```

- [ ] **Step 3: Typecheck + commit**

```bash
cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit
git add frontend/src/features/lots/AllLotsPage.tsx frontend/src/i18n/locales/de.ts
git commit -m "feat(lots): AllLotsPage cross-object view"
```

---

## Task 17: Frontend — `AllSuppliersPage` component

**Files:**
- Create: `frontend/src/features/suppliers/AllSuppliersPage.tsx`

- [ ] **Step 1: Create the file**

```tsx
/**
 * Cross-object supplier list.
 */
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { useAllSuppliers } from "./api";
import type { SupplierListItem } from "./types";

export function AllSuppliersPage(): JSX.Element {
  const { t } = useTranslation();
  const q = useAllSuppliers();

  return (
    <PageContainer width="default">
      <PageHeader
        title={t("suppliers.allTitle")}
        subtitle={t("suppliers.allSubtitle")}
      />

      {q.isLoading && <p className="text-slate-500">{t("common.loading")}</p>}
      {q.isError && <p className="text-red-700">{t("common.error")}</p>}
      {q.isSuccess && q.data.length === 0 && (
        <p className="text-slate-500">{t("suppliers.empty")}</p>
      )}
      {q.isSuccess && q.data.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-slate-600">
            <tr className="border-b border-slate-300">
              <th className="px-2 py-2">{t("suppliers.fields.name")}</th>
              <th className="px-2 py-2">{t("suppliers.fields.object")}</th>
              <th className="px-2 py-2">{t("suppliers.fields.email")}</th>
              <th className="px-2 py-2">{t("suppliers.fields.phone")}</th>
            </tr>
          </thead>
          <tbody>
            {q.data.map((s: SupplierListItem) => (
              <tr
                key={s.id}
                data-testid={`all-supplier-row-${s.id}`}
                className="border-b border-slate-200 hover:bg-slate-50"
              >
                <td className="px-2 py-2 font-medium">
                  <Link to={`/lieferanten/${s.id}`} className="hover:underline">
                    {s.name}
                  </Link>
                </td>
                <td className="px-2 py-2">
                  <Link
                    to={`/objekte/${s.object_id}`}
                    className="text-slate-600 underline-offset-2 hover:underline"
                  >
                    {s.object_name}
                  </Link>
                </td>
                <td className="px-2 py-2">{s.contact_email ?? "—"}</td>
                <td className="px-2 py-2">{s.contact_phone ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </PageContainer>
  );
}
```

- [ ] **Step 2: Add i18n keys** to `de.ts` under `suppliers: {`:

```ts
    allTitle: "Alle Lieferanten",
    allSubtitle: "Alle Lieferanten über alle Objekte",
    fields: {
      // ... existing
      object: "Objekt",
    },
```

- [ ] **Step 3: Typecheck + commit**

```bash
cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit
git add frontend/src/features/suppliers/AllSuppliersPage.tsx frontend/src/i18n/locales/de.ts
git commit -m "feat(suppliers): AllSuppliersPage cross-object view"
```

---

## Task 18: Frontend — rename `/projects/:id` route to `/projekte/:id`

**Files:**
- Modify: `frontend/src/app/App.tsx`
- Modify: `frontend/src/features/projects/ProjectsPage.tsx`
- Modify: `frontend/src/components/AppLayout.tsx`

The backend API path `/api/v1/projects/{id}` stays English (REST resource path). Only the **frontend route** is renamed for consistency with `/lose/:id` and `/lieferanten/:id`.

- [ ] **Step 1: Rename the route in `App.tsx:82`**

Change:
```tsx
<Route path="/projects/:projectId" element={<ProjectDetailPage />} />
```
to:
```tsx
<Route path="/projekte/:projectId" element={<ProjectDetailPage />} />
```

- [ ] **Step 2: Update the only consumer in `ProjectsPage.tsx:104`**

Change:
```tsx
<Link to={`/projects/${p.id}`} className="hover:underline">
```
to:
```tsx
<Link to={`/projekte/${p.id}`} className="hover:underline">
```

- [ ] **Step 3: Update `AppLayout.tsx` — DETAIL_ID_PATTERNS**

Find:
```tsx
const DETAIL_ID_PATTERNS = {
  projects: /^\/projects\/([^/]+)(?:\/|$)/,
  lose: /^\/lose\/([^/]+)(?:\/|$)/,
  lieferanten: /^\/lieferanten\/([^/]+)(?:\/|$)/,
} as const;
```

The `projects` key here is internal to AppLayout — keep the key name `projects` (it's a TypeScript discriminator, not a URL fragment) but change the regex to match `/projekte/` AND require a non-empty slug (so it doesn't match the bare `/projekte` cross-object list page):

```tsx
const DETAIL_ID_PATTERNS = {
  projects: /^\/projekte\/([^/]+)/,
  lose: /^\/lose\/([^/]+)/,
  lieferanten: /^\/lieferanten\/([^/]+)/,
} as const;
```

(Removing the `(?:\/|$)` is fine — `([^/]+)` already won't match the empty string after `/projekte/`, so `/projekte` alone won't match. Test this mentally: `"/projekte".match(/^\/projekte\/([^/]+)/)` → null. ✓.)

- [ ] **Step 4: Update `AppLayout.tsx` — useBreadcrumbs**

Find the existing branch:
```tsx
    } else if (parts[0] === "projects" && parts[1]) {
```

Change to:
```tsx
    } else if (parts[0] === "projekte" && parts[1]) {
```

(The `&& parts[1]` guard already ensures we don't treat `/projekte` bare as a detail page — the breadcrumb branch for the top-level list will be added in Task 20.)

- [ ] **Step 5: Verify no other refs**

Run: `grep -rn '"/projects/\|\`/projects/' frontend/src/`
Expected output: only the 4 lines in `frontend/src/features/projects/api.ts` (these are API paths, must stay).

- [ ] **Step 6: Typecheck + test + commit**

```bash
cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit && npm test -- --run
git add frontend/src/app/App.tsx frontend/src/features/projects/ProjectsPage.tsx frontend/src/components/AppLayout.tsx
git commit -m "refactor(routes): /projects/:id → /projekte/:id for consistency"
```

If tests fail because a test asserted `/projects/<uuid>` somewhere — update the test to use `/projekte/<uuid>`.

---

## Task 19: Frontend — add the three new top-level routes to `App.tsx`

**Files:**
- Modify: `frontend/src/app/App.tsx`

- [ ] **Step 1: Add imports**

```tsx
import { AllProjectsPage } from "@/features/projects/AllProjectsPage";
import { AllLotsPage } from "@/features/lots/AllLotsPage";
import { AllSuppliersPage } from "@/features/suppliers/AllSuppliersPage";
```

- [ ] **Step 2: Add three routes inside the authenticated route block**

After the existing `<Route path="/finanzen" element={<FinancesPage />} />` line (or anywhere inside the `<Route element={<RequireAuth><AppLayout /></RequireAuth>}>` parent — order doesn't affect matching for non-overlapping paths), add:

```tsx
<Route path="/projekte" element={<AllProjectsPage />} />
<Route path="/lose-uebersicht" element={<AllLotsPage />} />
<Route path="/lieferanten-uebersicht" element={<AllSuppliersPage />} />
```

Note: the detail routes `/projekte/:projectId`, `/lose/:lotId`, `/lieferanten/:supplierId` continue to coexist with these — react-router-dom v6 prefers exact matches over parametric, so `/projekte` → list, `/projekte/<uuid>` → detail. **Verify in Task 23's manual smoke.**

- [ ] **Step 3: Typecheck + commit**

```bash
cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit
git add frontend/src/app/App.tsx
git commit -m "feat(routes): top-level /projekte, /lose-uebersicht, /lieferanten-uebersicht"
```

---

## Task 20: Frontend — sidebar nav + breadcrumbs for the new top-level lists

**Files:**
- Modify: `frontend/src/components/AppLayout.tsx`
- Modify: `frontend/src/i18n/locales/de.ts`

- [ ] **Step 1: Add new i18n keys** under `nav` in `de.ts`:

```ts
projektsListe: "Projekte",
lotsListe: "Lose",
suppliersListe: "Lieferanten",
```

And under `nav.crumb`:
```ts
projektsListe: "Projekte (alle)",
lotsListe: "Lose (alle)",
suppliersListe: "Lieferanten (alle)",
```

(The "(alle)" suffix on breadcrumbs distinguishes these from the per-object breadcrumbs that already use `nav.crumb.projects` / `nav.crumb.lots` / `nav.crumb.suppliers`.)

- [ ] **Step 2: Add sidebar SidebarLinks in `AppLayout.tsx`**

Find the existing main-nav block inside `AppLayout`'s render that contains the four top-level SidebarLinks (Home, Objekte, Finanzen, [Admin-Audit if superuser]). Between Objekte and Finanzen, insert three new SidebarLinks:

```tsx
<SidebarLink
  to="/projekte"
  icon="🗂️"
  onNavigate={() => setDrawerOpen(false)}
>
  {t("nav.projektsListe")}
</SidebarLink>
<SidebarLink
  to="/lose-uebersicht"
  icon="📦"
  onNavigate={() => setDrawerOpen(false)}
>
  {t("nav.lotsListe")}
</SidebarLink>
<SidebarLink
  to="/lieferanten-uebersicht"
  icon="🤝"
  onNavigate={() => setDrawerOpen(false)}
>
  {t("nav.suppliersListe")}
</SidebarLink>
```

- [ ] **Step 3: Add breadcrumb branches** in `useBreadcrumbs` in `AppLayout.tsx`

Find the existing `else if (parts[0] === "finanzen")` branch. Before it (or anywhere among the top-level branches), add:

```tsx
    } else if (parts[0] === "projekte" && !parts[1]) {
      crumbs.push({ label: t("nav.crumb.projektsListe") });
    } else if (parts[0] === "lose-uebersicht") {
      crumbs.push({ label: t("nav.crumb.lotsListe") });
    } else if (parts[0] === "lieferanten-uebersicht") {
      crumbs.push({ label: t("nav.crumb.suppliersListe") });
```

The first one is gated by `!parts[1]` because `/projekte/<id>` is a detail page handled elsewhere.

- [ ] **Step 4: Typecheck + tests + commit**

```bash
cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit && npm test -- --run
git add frontend/src/components/AppLayout.tsx frontend/src/i18n/locales/de.ts
git commit -m "feat(layout): top-level nav + breadcrumbs for cross-object lists"
```

---

## Task 21: Frontend — render-smoke tests for the three new pages

**Files:**
- Create: `frontend/tests/AllProjectsPage.test.tsx`
- Create: `frontend/tests/AllLotsPage.test.tsx`
- Create: `frontend/tests/AllSuppliersPage.test.tsx`

Mirror the shape of `tests/budget/FinancesPage.test.tsx`. Mock the api hook; render; assert rows show + empty case.

- [ ] **Step 1: Find the existing FinancesPage test for reference**

Run: `cat /Users/stefan/Code/reno-budget/frontend/tests/budget/FinancesPage.test.tsx | head -60`

Use its mocking pattern (`vi.mock("@/features/budget/api", ...)`) as the template.

- [ ] **Step 2: Create `frontend/tests/AllProjectsPage.test.tsx`**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n/i18n";
import { AllProjectsPage } from "@/features/projects/AllProjectsPage";

vi.mock("@/features/projects/api", async () => {
  const actual = await vi.importActual<typeof import("@/features/projects/api")>(
    "@/features/projects/api",
  );
  return {
    ...actual,
    useAllProjects: vi.fn(),
  };
});

import { useAllProjects } from "@/features/projects/api";

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <I18nextProvider i18n={i18n}>
        <MemoryRouter>
          <AllProjectsPage />
        </MemoryRouter>
      </I18nextProvider>
    </QueryClientProvider>,
  );
}

describe("AllProjectsPage", () => {
  it("renders rows with project name and parent object", () => {
    vi.mocked(useAllProjects).mockReturnValue({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          object_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
          object_name: "Haus A",
          name: "Dach sanieren",
          description: null,
          status: "planned",
          planned_year: 2027,
          archived_at: null,
          created_by: null,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
    } as never);

    renderPage();
    expect(screen.getByText("Dach sanieren")).toBeInTheDocument();
    expect(screen.getByText("Haus A")).toBeInTheDocument();
  });

  it("renders empty state", () => {
    vi.mocked(useAllProjects).mockReturnValue({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: [],
    } as never);
    renderPage();
    // The empty-state key is "projects.empty" which is shared.
    expect(screen.getByText(/keine projekte|no projects|empty/i)).toBeInTheDocument();
  });
});
```

If the existing `projects.empty` translation is something other than the regex above, adjust. Inspect `de.ts` to confirm.

- [ ] **Step 3: Create `frontend/tests/AllLotsPage.test.tsx`** — mirror the above with lot fields. Use:

```tsx
vi.mock("@/features/lots/api", ...);
// data row:
{
  id: "...",
  object_id: "...",
  object_name: "Haus A",
  name: "Los 1",
  description: null,
  status: "draft",
  tender_deadline: null,
  awarded_quote_id: null,
  archived_at: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  cost_item_count: 0,
  cost_item_ids: [],
}
```

- [ ] **Step 4: Create `frontend/tests/AllSuppliersPage.test.tsx`** — mirror with supplier fields:

```tsx
{
  id: "...",
  object_id: "...",
  object_name: "Haus A",
  name: "Firma A",
  contact_email: "info@firma.ch",
  contact_phone: null,
  address: null,
  notes: null,
  archived_at: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}
```

- [ ] **Step 5: Run the three tests**

Run: `cd /Users/stefan/Code/reno-budget/frontend && npm test -- --run AllProjectsPage AllLotsPage AllSuppliersPage`
Expected: all 6 tests pass (2 per file).

- [ ] **Step 6: Commit**

```bash
git add frontend/tests/AllProjectsPage.test.tsx frontend/tests/AllLotsPage.test.tsx frontend/tests/AllSuppliersPage.test.tsx
git commit -m "test(cross-object): render-smoke tests for the three new pages"
```

---

## Task 22: Full test suite + lint + typecheck

**Files:** None — verification only.

- [ ] **Step 1: Backend tests**

Run: `cd /Users/stefan/Code/reno-budget/backend && pytest -x --tb=short`
Expected: all pass.

- [ ] **Step 2: Frontend tests**

Run: `cd /Users/stefan/Code/reno-budget/frontend && npm test -- --run`
Expected: all pass.

- [ ] **Step 3: Frontend typecheck**

Run: `cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 4: Frontend lint**

Run: `cd /Users/stefan/Code/reno-budget/frontend && npm run lint`
Expected: 0 errors. Pre-existing warnings in TimelineChart/budget/types.ts are acceptable; anything new must be silenced or fixed.

- [ ] **Step 5: Commit any fixups** (probably none).

---

## Task 23: Docker rebuild + smoke

**Files:** None — verification only.

- [ ] **Step 1: Rebuild both `web` and `api` images**

The API changes (new endpoints) need rebuilding too.

```bash
docker compose -f /Users/stefan/Code/reno-budget/deploy/docker-compose.yml build api web
docker compose -f /Users/stefan/Code/reno-budget/deploy/docker-compose.yml up -d api web
```

- [ ] **Step 2: Verify containers healthy**

```bash
docker compose -f /Users/stefan/Code/reno-budget/deploy/docker-compose.yml ps
```
Expected: api, web both `Up (healthy)`.

- [ ] **Step 3: Programmatic smoke**

```bash
# Frontend bundles up:
curl -sf http://localhost:8080/ -o /dev/null && echo "web 200"
# Backend new endpoints respond (unauthenticated → 401 is the right answer; that confirms route registered):
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/v1/projects
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/v1/lots
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/api/v1/suppliers
```
Expected: all 3 backend paths return 401 (not 404). 401 confirms the routes exist but auth is required. 404 means the route didn't register — investigate.

- [ ] **Step 4: Manual visual smoke**

Open http://localhost:8080 in browser. Log in. Verify:
- Three new top-level sidebar links visible: Projekte, Lose, Lieferanten (between Objekte and Finanzen)
- Click Projekte → see cross-object list, breadcrumb is "Start › Projekte (alle)"
- Click a project name → goes to `/projekte/<uuid>` (detail page)
- Click the parent object name → goes to `/objekte/<uuid>` (object detail)
- Same for Lose-Übersicht → `/lose-uebersicht`, and Lieferanten-Übersicht → `/lieferanten-uebersicht`
- Per-object pages still work: navigate into an object → its per-object Projekte/Lose/Lieferanten still load and link to detail pages
- Breadcrumbs distinguish: top-level list shows "Projekte (alle)"; per-object shows "Start › Objekte › <Name> › Projekte"

---

## Task 24: Push branch + open PR

**Files:** None — git only.

- [ ] **Step 1: Verify branch state**

Run: `git log --oneline main..HEAD | head -30`
Expected: a clean series of atomic commits from Tasks 1-23.

- [ ] **Step 2: Push**

```bash
cd /Users/stefan/Code/reno-budget && git push -u origin feat/cross-object-lists
```

- [ ] **Step 3: PR body (write to `.pr-body.md` since `gh` may not be installed)**

```markdown
## Summary

Add cross-object top-level list pages for Projects / Lots / Suppliers. Each is one row per resource across every object the user has access to, with a link to the resource detail and to its parent object. Also normalizes the frontend `/projects/:id` route to `/projekte/:id` for consistency with the already-German `/lose/:id` and `/lieferanten/:id`.

## What changed

### Backend (FastAPI + SQLAlchemy async)
- 3 new endpoints under existing routers:
  - `GET /api/v1/projects` (in `router_projects`)
  - `GET /api/v1/lots` (in `router_lots`)
  - `GET /api/v1/suppliers` (in `router_suppliers`)
- Each enumerates `list_objects_for_user(session, user.id)` then per-object calls the existing `list_<resource>` service. Archived rows excluded.
- 3 new Pydantic schemas (`ProjectListItem`, `LotListItem`, `SupplierListItem`) — each extends the corresponding `<Resource>Read` with a single `object_name: str` field.
- 5 integration tests covering RBAC isolation, archived exclusion, empty case, and the new `object_name` field.

### Frontend
- 3 new pages: `AllProjectsPage`, `AllLotsPage`, `AllSuppliersPage` at `/projekte`, `/lose-uebersicht`, `/lieferanten-uebersicht`.
- 3 new sidebar nav entries between Objekte and Finanzen.
- Breadcrumb branches for each new top-level route.
- Route normalization: `/projects/:projectId` → `/projekte/:projectId` (single rename, two consumer updates).
- 6 render-smoke tests (2 per new page).

### Out of scope
- Archived toggle on the cross-object lists (backend supports it via query param trivially; UI added when needed)
- Cross-object search / filtering
- Pagination

## Test plan
- [x] Backend pytest — all pass including 5 new
- [x] Frontend vitest — all pass including 6 new
- [x] `npx tsc --noEmit` clean
- [x] `npm run lint` 0 errors
- [x] Docker `api` and `web` images rebuild clean, containers healthy
- [x] Programmatic smoke: new backend routes return 401 (not 404)
- [ ] **Manual visual smoke** (please verify):
  - Three new sidebar links visible between Objekte and Finanzen
  - Top-level list pages show one row per resource across all objects
  - Clicking a project name navigates to `/projekte/<id>` detail
  - Clicking an object name navigates to `/objekte/<id>`
  - Per-object resource pages still work and still link to detail pages
  - Breadcrumbs distinguish top-level list ("Projekte (alle)") from per-object ("Objekte › Haus X › Projekte")

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 4: Open the PR**

If `gh` CLI is installed: `gh pr create --title "feat(cross-object): top-level Projects/Lots/Suppliers lists + /projekte route normalization" --body-file .pr-body.md`

Otherwise open via GitHub web at: `https://github.com/<owner>/<repo>/pull/new/feat/cross-object-lists`

- [ ] **Step 5: Return the PR URL**
