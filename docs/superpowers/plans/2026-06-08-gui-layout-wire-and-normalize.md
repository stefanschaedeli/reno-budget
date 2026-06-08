# GUI Layout Wire-Up + Header Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the orphaned `AppLayout` into the router so every authenticated page renders inside a sidebar + breadcrumb chrome, extend the layout to cover all current routes (Projekte / Lose / Lieferanten / Tags), and strip the duplicated page-header markup from all 14 authenticated pages.

**Architecture:** Convert the flat route table in `App.tsx` to a nested tree with `AppLayout` as the parent of all authenticated routes (children render via `<Outlet />`). Introduce a small `PageHeader` component the layout consumes via context so each page can declare its title/subtitle/primary-action declaratively. Extend `useBreadcrumbs` and `ObjectContextSection` in `AppLayout.tsx` to cover the new resources. Adopt the orphaned `lib/apiError.ts` helper across feature API clients to standardize error text. Out of scope: cross-object top-level Projects/Lots/Suppliers pages (planned for PR 2 — needs new backend endpoints).

**Tech Stack:** React 18 + TypeScript, react-router-dom v6 (nested routes + `<Outlet />`), TanStack Query, Tailwind, i18next.

---

## File Structure

**Created:**
- `frontend/src/components/PageHeader.tsx` — title/subtitle/actions container rendered inside `AppLayout`'s sticky header area
- `frontend/src/components/PageContainer.tsx` — standardized `mx-auto max-w-* p-6` wrapper page bodies use instead of rolling their own
- `frontend/src/components/Drawer.tsx` — extracted from CostsPage/ProjectsPage/LotsPage/SuppliersPage (currently duplicated 4×)

**Modified:**
- `frontend/src/components/AppLayout.tsx` — extend breadcrumbs + nav links, mount PageHeader slot
- `frontend/src/app/App.tsx` — nested route tree
- `frontend/src/features/auth/HomePage.tsx` — drop own user-menu chrome (layout owns it)
- `frontend/src/features/objects/{ObjectsListPage,ObjectCreatePage,ObjectDetailPage}.tsx`
- `frontend/src/features/costs/CostsPage.tsx`
- `frontend/src/features/budget/{BudgetPage,FinancesPage}.tsx`
- `frontend/src/features/renofond/RenofondPage.tsx`
- `frontend/src/features/projects/{ProjectsPage,ProjectDetailPage}.tsx`
- `frontend/src/features/lots/{LotsPage,LotDetailPage}.tsx`
- `frontend/src/features/suppliers/{SuppliersPage,SupplierDetailPage}.tsx`
- `frontend/src/features/audit/AuditPage.tsx`
- Various `frontend/src/features/*/api.ts` — adopt `apiErrorMessage` helper

**Deleted (after extraction):**
- Inline `Drawer` definitions in `CostsPage.tsx`, `ProjectsPage.tsx`, `LotsPage.tsx`, `SuppliersPage.tsx`

---

## Task 1: Extract shared `PageContainer` component

**Files:**
- Create: `frontend/src/components/PageContainer.tsx`

The audit found 3 page widths (`max-w-3xl`, `max-w-5xl`, `max-w-6xl`) used inconsistently across pages. A `width` prop normalizes this — each page declares its width once.

- [ ] **Step 1: Create `PageContainer.tsx`**

```tsx
import type { ReactNode } from "react";

type Width = "narrow" | "default" | "wide";

const WIDTH_CLASS: Record<Width, string> = {
  narrow: "max-w-3xl",   // forms, detail pages
  default: "max-w-5xl",  // list pages
  wide: "max-w-6xl",     // dashboards (budget, renofond)
};

export function PageContainer({
  width = "default",
  children,
}: {
  width?: Width;
  children: ReactNode;
}): JSX.Element {
  return (
    <div className={`mx-auto ${WIDTH_CLASS[width]} p-6`}>{children}</div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/PageContainer.tsx
git commit -m "feat(layout): add PageContainer for consistent page widths"
```

---

## Task 2: Extract shared `PageHeader` component

**Files:**
- Create: `frontend/src/components/PageHeader.tsx`

Replaces the per-page `<header className="mb-N flex items-center justify-between"><h2>...</h2>...</header>` pattern. The `actions` slot takes the right-aligned primary action button(s).

- [ ] **Step 1: Create `PageHeader.tsx`**

```tsx
import type { ReactNode } from "react";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}): JSX.Element {
  return (
    <header className="mb-6 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="text-2xl font-semibold">{title}</h2>
        {subtitle && (
          <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      )}
    </header>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/PageHeader.tsx
git commit -m "feat(layout): add PageHeader for consistent page titles"
```

---

## Task 3: Extract shared `Drawer` component

**Files:**
- Create: `frontend/src/components/Drawer.tsx`

`CostsPage.tsx:260-290`, `ProjectsPage.tsx:136-166`, `LotsPage.tsx:131-161`, `SuppliersPage.tsx:127-157` all define identical `Drawer` components. Extract once.

- [ ] **Step 1: Create `Drawer.tsx`** (verbatim from `CostsPage.tsx:260-290`, adjusted for shared use)

```tsx
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

interface DrawerProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function Drawer({ title, onClose, children }: DrawerProps): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="fixed inset-0 z-40 flex">
      <div
        className="flex-1 bg-slate-900/40"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside className="z-50 w-full max-w-xl overflow-y-auto bg-white p-6 shadow-xl">
        <header className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common.close")}
            className="text-slate-500 hover:text-slate-900"
          >
            ×
          </button>
        </header>
        {children}
      </aside>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Drawer.tsx
git commit -m "refactor(layout): extract shared Drawer component"
```

---

## Task 4: Extend `useBreadcrumbs` to cover all routes

**Files:**
- Modify: `frontend/src/components/AppLayout.tsx:41-76`

Current `useBreadcrumbs` only handles `/objekte`, `/finanzen`, `/admin/audit`. Add cases for `/objekte/:id/projekte`, `/objekte/:id/lose`, `/objekte/:id/lieferanten`, `/projects/:id`, `/lose/:id`, `/lieferanten/:id`. The detail pages need to fetch their parent object's name — we'll keep that simple: show "…" placeholder until loaded, mirroring the existing pattern for object name.

- [ ] **Step 1: Add detail-page name hooks** at the top of `AppLayout.tsx` near `useObjectName` (around line 31). Insert after the `useObjectName` function:

```tsx
function useProjectName(id: string | null): { name: string | undefined; objectId: string | undefined } {
  const q = useQuery({
    queryKey: ["project-name", id],
    queryFn: async () => {
      const { getProject } = await import("@/features/projects/api");
      return getProject(id as string);
    },
    enabled: !!id,
    staleTime: 60_000,
  });
  return { name: q.data?.name, objectId: q.data?.object_id };
}

function useLotName(id: string | null): { name: string | undefined; objectId: string | undefined } {
  const q = useQuery({
    queryKey: ["lot-name", id],
    queryFn: async () => {
      const { getLot } = await import("@/features/lots/api");
      return getLot(id as string);
    },
    enabled: !!id,
    staleTime: 60_000,
  });
  return { name: q.data?.name, objectId: q.data?.object_id };
}

function useSupplierName(id: string | null): { name: string | undefined; objectId: string | undefined } {
  const q = useQuery({
    queryKey: ["supplier-name", id],
    queryFn: async () => {
      const { getSupplier } = await import("@/features/suppliers/api");
      return getSupplier(id as string);
    },
    enabled: !!id,
    staleTime: 60_000,
  });
  return { name: q.data?.name, objectId: q.data?.object_id };
}
```

> **Note:** dynamic `import()` is used so the layout doesn't statically pull every feature's API into the initial bundle. If feature APIs are tiny (they are), feel free to switch to static imports — both work.

- [ ] **Step 2: Add route-ID extraction helpers** alongside `useCurrentObjectId` (around line 22):

```tsx
function useCurrentDetailId(prefix: "projects" | "lose" | "lieferanten"): string | null {
  const { pathname } = useLocation();
  const m = pathname.match(new RegExp(`^/${prefix}/([^/]+)(?:/|$)`));
  return m ? m[1]! : null;
}
```

- [ ] **Step 3: Extend `useBreadcrumbs`** at `AppLayout.tsx:41-76`. Replace the existing body with:

```tsx
function useBreadcrumbs(
  objectName: string | undefined,
  projectName: { name: string | undefined; objectId: string | undefined },
  lotName: { name: string | undefined; objectId: string | undefined },
  supplierName: { name: string | undefined; objectId: string | undefined },
): Crumb[] {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  return useMemo(() => {
    const parts = pathname.split("/").filter(Boolean);
    const crumbs: Crumb[] = [{ label: t("nav.crumb.home"), to: "/" }];
    if (parts.length === 0) return [{ label: t("nav.crumb.home") }];

    if (parts[0] === "objekte") {
      crumbs.push({ label: t("nav.crumb.objects"), to: "/objekte" });
      if (parts[1] === "neu") {
        crumbs.push({ label: t("nav.crumb.newObject") });
      } else if (parts[1]) {
        const objId = parts[1];
        crumbs.push({ label: objectName ?? "…", to: `/objekte/${objId}` });
        const tail = parts[2];
        if (tail === "kosten") crumbs.push({ label: t("nav.crumb.costs") });
        else if (tail === "budget") crumbs.push({ label: t("nav.crumb.budget") });
        else if (tail === "renofond") crumbs.push({ label: t("nav.crumb.renofond") });
        else if (tail === "audit") crumbs.push({ label: t("nav.crumb.audit") });
        else if (tail === "projekte") crumbs.push({ label: t("nav.crumb.projects") });
        else if (tail === "lose") crumbs.push({ label: t("nav.crumb.lots") });
        else if (tail === "lieferanten") crumbs.push({ label: t("nav.crumb.suppliers") });
      }
    } else if (parts[0] === "projects" && parts[1]) {
      // Detail-page breadcrumb: try to thread the parent object in if we know it
      if (projectName.objectId) {
        crumbs.push({ label: t("nav.crumb.objects"), to: "/objekte" });
        crumbs.push({ label: "…", to: `/objekte/${projectName.objectId}` });
        crumbs.push({
          label: t("nav.crumb.projects"),
          to: `/objekte/${projectName.objectId}/projekte`,
        });
      } else {
        crumbs.push({ label: t("nav.crumb.projects") });
      }
      crumbs.push({ label: projectName.name ?? "…" });
    } else if (parts[0] === "lose" && parts[1]) {
      if (lotName.objectId) {
        crumbs.push({ label: t("nav.crumb.objects"), to: "/objekte" });
        crumbs.push({ label: "…", to: `/objekte/${lotName.objectId}` });
        crumbs.push({
          label: t("nav.crumb.lots"),
          to: `/objekte/${lotName.objectId}/lose`,
        });
      } else {
        crumbs.push({ label: t("nav.crumb.lots") });
      }
      crumbs.push({ label: lotName.name ?? "…" });
    } else if (parts[0] === "lieferanten" && parts[1]) {
      if (supplierName.objectId) {
        crumbs.push({ label: t("nav.crumb.objects"), to: "/objekte" });
        crumbs.push({ label: "…", to: `/objekte/${supplierName.objectId}` });
        crumbs.push({
          label: t("nav.crumb.suppliers"),
          to: `/objekte/${supplierName.objectId}/lieferanten`,
        });
      } else {
        crumbs.push({ label: t("nav.crumb.suppliers") });
      }
      crumbs.push({ label: supplierName.name ?? "…" });
    } else if (parts[0] === "finanzen") {
      crumbs.push({ label: t("nav.crumb.finances") });
    } else if (parts[0] === "admin") {
      crumbs.push({ label: t("nav.crumb.admin") });
      if (parts[1] === "audit") crumbs.push({ label: t("nav.crumb.adminAudit") });
    }
    const last = crumbs[crumbs.length - 1];
    if (last) delete last.to;
    return crumbs;
  }, [pathname, objectName, projectName, lotName, supplierName, t]);
}
```

- [ ] **Step 4: Update `AppLayout` to call the new hooks** at lines 295-303. Replace:

```tsx
  const objectId = useCurrentObjectId();
  const objectName = useObjectName(objectId);
  const crumbs = useBreadcrumbs(objectName);
```

with:

```tsx
  const objectId = useCurrentObjectId();
  const objectName = useObjectName(objectId);
  const projectId = useCurrentDetailId("projects");
  const projectInfo = useProjectName(projectId);
  const lotId = useCurrentDetailId("lose");
  const lotInfo = useLotName(lotId);
  const supplierId = useCurrentDetailId("lieferanten");
  const supplierInfo = useSupplierName(supplierId);

  // If we're on a detail page, derive the object id from its parent for the
  // ObjectContextSection sidebar block.
  const effectiveObjectId =
    objectId ?? projectInfo.objectId ?? lotInfo.objectId ?? supplierInfo.objectId ?? null;
  const effectiveObjectName =
    objectName ?? (effectiveObjectId ? undefined : undefined);

  const crumbs = useBreadcrumbs(objectName, projectInfo, lotInfo, supplierInfo);
```

- [ ] **Step 5: Verify `getProject` / `getLot` / `getSupplier` exist with the right shape**

Run: `grep -n "export.*function getProject\|export.*function getLot\|export.*function getSupplier" /Users/stefan/Code/reno-budget/frontend/src/features/{projects,lots,suppliers}/api.ts`

Expected: each file exports a `getProject(id)` / `getLot(id)` / `getSupplier(id)` returning an object with `name` and `object_id`. If the function is named differently (e.g. `fetchProject`), adjust the dynamic import. If it returns a different shape, adjust the `useQuery` selector. Don't proceed until this matches.

- [ ] **Step 6: Add the new i18n keys to `frontend/src/i18n/locales/de.ts` and `en.ts`**

Add under `nav.crumb`:
- `projects: "Projekte"` (de) / `"Projects"` (en)
- `lots: "Lose"` (de) / `"Lots"` (en)
- `suppliers: "Lieferanten"` (de) / `"Suppliers"` (en)

Run: `grep -n "nav.crumb" /Users/stefan/Code/reno-budget/frontend/src/i18n/locales/de.ts` to find the section and add the keys alongside the existing crumb keys.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/AppLayout.tsx frontend/src/i18n/locales/
git commit -m "feat(layout): breadcrumbs for projekte/lose/lieferanten + detail pages"
```

---

## Task 5: Extend `ObjectContextSection` sidebar with new nav links

**Files:**
- Modify: `frontend/src/components/AppLayout.tsx:112-170`

Add Projekte / Lose / Lieferanten to the per-object sidebar block.

- [ ] **Step 1: Insert three new `SidebarLink` entries** between the existing `nav.crumb.budget` (line 152) link and the `nav.crumb.renofond` link (line 154-159). Replace the existing block from line 130 onwards:

```tsx
      <div className="space-y-1">
        <SidebarLink
          to={`/objekte/${objectId}`}
          end
          icon="🏢"
          onNavigate={onNavigate}
        >
          {t("objects.units.title")}
        </SidebarLink>
        <SidebarLink
          to={`/objekte/${objectId}/kosten`}
          icon="📝"
          onNavigate={onNavigate}
        >
          {t("nav.crumb.costs")}
        </SidebarLink>
        <SidebarLink
          to={`/objekte/${objectId}/budget`}
          icon="📊"
          onNavigate={onNavigate}
        >
          {t("nav.crumb.budget")}
        </SidebarLink>
        <SidebarLink
          to={`/objekte/${objectId}/projekte`}
          icon="🗂️"
          onNavigate={onNavigate}
        >
          {t("nav.crumb.projects")}
        </SidebarLink>
        <SidebarLink
          to={`/objekte/${objectId}/lose`}
          icon="📦"
          onNavigate={onNavigate}
        >
          {t("nav.crumb.lots")}
        </SidebarLink>
        <SidebarLink
          to={`/objekte/${objectId}/lieferanten`}
          icon="🤝"
          onNavigate={onNavigate}
        >
          {t("nav.crumb.suppliers")}
        </SidebarLink>
        <SidebarLink
          to={`/objekte/${objectId}/renofond`}
          icon="📈"
          onNavigate={onNavigate}
        >
          {t("nav.crumb.renofond")}
        </SidebarLink>
        <SidebarLink
          to={`/objekte/${objectId}/audit`}
          icon="📜"
          onNavigate={onNavigate}
        >
          {t("nav.crumb.audit")}
        </SidebarLink>
      </div>
```

- [ ] **Step 2: Pass `effectiveObjectId` instead of `objectId`** at line 385-391 so the per-object section also appears on detail pages (e.g. `/projects/:id`):

Replace:
```tsx
          {objectId && (
            <ObjectContextSection
              objectId={objectId}
              objectName={objectName}
              onNavigate={() => setDrawerOpen(false)}
            />
          )}
```

with:
```tsx
          {effectiveObjectId && (
            <ObjectContextSection
              objectId={effectiveObjectId}
              objectName={effectiveObjectName}
              onNavigate={() => setDrawerOpen(false)}
            />
          )}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AppLayout.tsx
git commit -m "feat(layout): sidebar links for projekte/lose/lieferanten"
```

---

## Task 6: Wire `AppLayout` into the router

**Files:**
- Modify: `frontend/src/app/App.tsx:52-196`

Restructure the flat `<Routes>` into a nested tree. Public routes (login/invite/password) stay as siblings. All authenticated routes become children of a single `<Route element={<RequireAuth><AppLayout/></RequireAuth>}>` parent.

- [ ] **Step 1: Add the AppLayout import** at the top of `App.tsx` (after line 8):

```tsx
import { AppLayout } from "@/components/AppLayout";
```

- [ ] **Step 2: Replace the entire `<Routes>` block** (lines 57-191) with:

```tsx
          <Routes>
            {/* Public routes */}
            <Route path="/anmelden" element={<LoginPage />} />
            <Route path="/invite/:token" element={<AcceptInvitePage />} />
            <Route path="/passwort-zuruecksetzen" element={<PasswordResetRequestPage />} />
            <Route path="/passwort-zuruecksetzen/:token" element={<PasswordResetConfirmPage />} />

            {/* Authenticated routes — all share AppLayout chrome */}
            <Route
              element={
                <RequireAuth>
                  <AppLayout />
                </RequireAuth>
              }
            >
              <Route path="/" element={<HomePage />} />
              <Route path="/objekte" element={<ObjectsListPage />} />
              <Route path="/objekte/neu" element={<ObjectCreatePage />} />
              <Route path="/objekte/:id" element={<ObjectDetailPage />} />
              <Route path="/objekte/:objectId/kosten" element={<CostsPage />} />
              <Route path="/objekte/:id/budget" element={<BudgetPage />} />
              <Route path="/objekte/:id/renofond" element={<RenofondPage />} />
              <Route path="/finanzen" element={<FinancesPage />} />
              <Route path="/objekte/:objectId/projekte" element={<ProjectsPage />} />
              <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
              <Route path="/objekte/:objectId/lose" element={<LotsPage />} />
              <Route path="/lose/:lotId" element={<LotDetailPage />} />
              <Route path="/objekte/:objectId/lieferanten" element={<SuppliersPage />} />
              <Route path="/lieferanten/:supplierId" element={<SupplierDetailPage />} />
              <Route path="/objekte/:id/audit" element={<ObjectAuditPage />} />
              <Route path="/admin/audit" element={<GlobalAuditPage />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
```

> **Note:** `RequireAuth` currently expects `children: React.ReactElement` (App.tsx:40). With the layout-wrapping approach above, we pass `<AppLayout />` as the child — `AppLayout` itself renders `<Outlet />` for the nested route's element. No change to `RequireAuth` is needed.

- [ ] **Step 3: Run typecheck**

Run: `cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit`
Expected: clean. If `AppLayout` is missing the `<Outlet />` import or there's a missing i18n key, fix before continuing.

- [ ] **Step 4: Run vite dev locally** (sanity, before docker rebuild)

Run: `cd /Users/stefan/Code/reno-budget/frontend && npm run dev`
Open http://localhost:5173 in a browser. Verify the sidebar + breadcrumbs appear on every authenticated page. Don't worry about page chrome duplication yet — that's Task 7+.

Kill the dev server before moving on.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/App.tsx
git commit -m "feat(router): wire AppLayout into nested routes for authenticated pages"
```

---

## Task 7: Normalize `HomePage`

**Files:**
- Modify: `frontend/src/features/auth/HomePage.tsx`

The layout now owns the user menu / logout / language switcher. HomePage should be a content-only page.

- [ ] **Step 1: Replace the entire file** with:

```tsx
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";

export function HomePage(): JSX.Element {
  const { t } = useTranslation();
  const { user } = useAuth();

  return (
    <PageContainer width="narrow">
      <PageHeader title={t("app.title")} subtitle={t("app.subtitle")} />
      {user && (
        <p className="mb-4 text-sm text-slate-500">
          {t("auth.me.greeting", { name: user.display_name })}
        </p>
      )}
      <nav className="flex gap-2">
        <Link
          to="/objekte"
          className="inline-block rounded bg-slate-900 px-3 py-2 text-sm text-white hover:bg-slate-700"
        >
          {t("objects.list.title")}
        </Link>
        <Link
          to="/finanzen"
          className="inline-block rounded border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100"
        >
          {t("budget.nav")}
        </Link>
      </nav>
    </PageContainer>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/features/auth/HomePage.tsx
git commit -m "refactor(home): drop own user-menu chrome; use PageContainer/Header"
```

---

## Task 8: Normalize `ObjectsListPage`

**Files:**
- Modify: `frontend/src/features/objects/ObjectsListPage.tsx`

- [ ] **Step 1: Replace lines 33-66** (the JSX returned by the component) with:

```tsx
  return (
    <PageContainer width="narrow">
      <PageHeader
        title={t("objects.list.title")}
        actions={
          <Link
            to="/objekte/neu"
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
          >
            {t("objects.list.create")}
          </Link>
        }
      />

      {error && <p className="text-red-700">{error}</p>}
      {objects === null && !error && <p className="text-slate-500">{t("common.loading")}</p>}
      {objects && objects.length === 0 && (
        <p className="text-slate-600">{t("objects.list.empty")}</p>
      )}
      {objects && objects.length > 0 && (
        <ul className="divide-y rounded border border-slate-200">
          {objects.map((o) => (
            <li key={o.id} className="p-3 hover:bg-slate-50">
              <Link to={`/objekte/${o.id}`} className="flex justify-between">
                <span className="font-medium">{o.name}</span>
                <span className="text-sm text-slate-500">
                  {t(`objects.type.${o.type}`)}
                </span>
              </Link>
              {o.address && <p className="text-sm text-slate-500">{o.address}</p>}
            </li>
          ))}
        </ul>
      )}
    </PageContainer>
  );
```

- [ ] **Step 2: Add imports** at the top (after the existing imports):

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/objects/ObjectsListPage.tsx
git commit -m "refactor(objects): use PageContainer/Header in list page"
```

---

## Task 9: Normalize `ObjectCreatePage`

**Files:**
- Modify: `frontend/src/features/objects/ObjectCreatePage.tsx`

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
```

- [ ] **Step 2: Replace lines 67-138** (`<section>...</section>`) with:

```tsx
  return (
    <PageContainer width="narrow">
      <PageHeader title={t("objects.create.title")} />
      <form onSubmit={(e) => void submit(e)} className="space-y-4">
        <label className="block">
          <span className="text-sm">{t("objects.fields.name")}</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
          />
        </label>

        <label className="block">
          <span className="text-sm">{t("objects.fields.address")}</span>
          <input
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
          />
        </label>

        <label className="block">
          <span className="text-sm">{t("objects.fields.yearBuilt")}</span>
          <input
            type="number"
            value={yearBuilt}
            onChange={(e) => setYearBuilt(e.target.value)}
            className="mt-1 w-32 rounded border border-slate-300 px-2 py-1"
          />
        </label>

        <fieldset>
          <legend className="text-sm">{t("objects.fields.type")}</legend>
          <label className="mr-4">
            <input
              type="radio"
              name="type"
              checked={type === "sfh"}
              onChange={() => onTypeChange("sfh")}
            />{" "}
            {t("objects.type.sfh")}
          </label>
          <label>
            <input
              type="radio"
              name="type"
              checked={type === "mfh"}
              onChange={() => onTypeChange("mfh")}
            />{" "}
            {t("objects.type.mfh")}
          </label>
        </fieldset>

        <section>
          <h3 className="mb-2 text-lg font-medium">{t("objects.units.title")}</h3>
          <UnitEditor units={units} onChange={setUnits} readonly={type === "sfh"} />
        </section>

        {error && <p className="text-red-700">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="rounded bg-slate-900 px-4 py-2 text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {busy ? t("common.submitting") : t("objects.create.submit")}
        </button>
      </form>
    </PageContainer>
  );
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/objects/ObjectCreatePage.tsx
git commit -m "refactor(objects): use PageContainer/Header in create page"
```

---

## Task 10: Normalize `ObjectDetailPage`

**Files:**
- Modify: `frontend/src/features/objects/ObjectDetailPage.tsx`

The inline tab-nav at lines 49-86 duplicates what the sidebar now offers — drop it.

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
```

- [ ] **Step 2: Replace lines 38-108** (error branch, loading branch, and the JSX) with:

```tsx
  if (error)
    return (
      <PageContainer width="narrow">
        <p className="text-red-700">{error}</p>
      </PageContainer>
    );
  if (!obj)
    return (
      <PageContainer width="narrow">
        <p className="text-slate-500">{t("common.loading")}</p>
      </PageContainer>
    );

  return (
    <PageContainer width="narrow">
      <PageHeader
        title={obj.name}
        subtitle={
          <>
            {t(`objects.type.${obj.type}`)}
            {obj.address && ` — ${obj.address}`}
          </>
        }
      />

      <section className="mb-8">
        <h3 className="mb-2 text-lg font-medium">{t("objects.units.title")}</h3>
        <UnitEditor
          units={obj.units.map((u) => ({
            label: u.label,
            wertquote_permille: u.wertquote_permille,
            area_m2: u.area_m2,
          }))}
          onChange={() => {
            /* read-only in Phase 2; see Phase 3 plan entry */
          }}
          readonly
        />
      </section>

      <section className="mb-8">
        <AttachmentList targetType="object" targetId={obj.id} canEdit />
      </section>
    </PageContainer>
  );
```

- [ ] **Step 3: Remove the now-unused `Link` import** at line 3 (the inline nav was the only consumer):

Change:
```tsx
import { Link, useParams } from "react-router-dom";
```
to:
```tsx
import { useParams } from "react-router-dom";
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/objects/ObjectDetailPage.tsx
git commit -m "refactor(objects): drop inline tab nav; use PageContainer/Header"
```

---

## Task 11: Normalize `CostsPage`

**Files:**
- Modify: `frontend/src/features/costs/CostsPage.tsx`

Page header subtitle is the object name. Drop the inline `Drawer` (Task 3 extracted it).

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { Drawer } from "@/components/Drawer";
```

- [ ] **Step 2: Replace lines 69-78** (error and loading branches) with:

```tsx
  if (loadError)
    return (
      <PageContainer width="wide">
        <p className="text-red-700">{loadError}</p>
      </PageContainer>
    );
  if (!obj || !objectId)
    return (
      <PageContainer width="wide">
        <p className="text-slate-500">{t("common.loading")}</p>
      </PageContainer>
    );
```

- [ ] **Step 3: Replace lines 115-129** (the outer `<section>` opening + header) with:

```tsx
  return (
    <PageContainer width="wide">
      <PageHeader
        title={t("costs.title")}
        subtitle={obj.name}
        actions={
          <button
            type="button"
            onClick={() => setEditing("new")}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
          >
            {t("costs.create")}
          </button>
        }
      />
```

- [ ] **Step 4: Change the closing `</section>` at line 257** to `</PageContainer>`.

- [ ] **Step 5: Delete the inline Drawer** at lines 260-290 (the entire `interface DrawerProps` and `function Drawer` declarations). The shared one is imported now.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/costs/CostsPage.tsx
git commit -m "refactor(costs): use PageContainer/Header + shared Drawer"
```

---

## Task 12: Normalize `BudgetPage`

**Files:**
- Modify: `frontend/src/features/budget/BudgetPage.tsx`

Drop the inline three-tab nav (lines 23-42) — sidebar now owns it. Keep export buttons as the primary action.

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
```

- [ ] **Step 2: Remove the `Link` import** at line 3 — only the dropped tab nav used it. Change:

```tsx
import { Link, useParams } from "react-router-dom";
```
to:
```tsx
import { useParams } from "react-router-dom";
```

- [ ] **Step 3: Replace lines 17-65** (`if (!id) return ...` plus the outer `<section>` opening through the export-links `</div>`) with:

```tsx
  if (!id)
    return (
      <PageContainer width="wide">
        <p className="text-red-700">{t("common.error")}</p>
      </PageContainer>
    );

  return (
    <PageContainer width="wide">
      <PageHeader
        title={t("budget.title")}
        actions={
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="self-center text-slate-500">{t("export.label")}:</span>
            <a
              href={`/api/v1/objects/${id}/export/xlsx`}
              className="rounded border border-slate-300 bg-white px-3 py-1 hover:bg-slate-50"
            >
              {t("export.xlsx")}
            </a>
            <a
              href={`/api/v1/objects/${id}/export/pdf`}
              className="rounded border border-slate-300 bg-white px-3 py-1 hover:bg-slate-50"
            >
              {t("export.pdf")}
            </a>
            <a
              href={`/api/v1/objects/${id}/export/npk`}
              className="rounded border border-slate-300 bg-white px-3 py-1 hover:bg-slate-50"
            >
              {t("export.npk")}
            </a>
          </div>
        }
      />

      <div className="space-y-6">
```

- [ ] **Step 4: Wrap the existing space-y-6 content inside the new opening div.** The component returns:
- ReservePanel
- TimelineChart wrapper
- Tab nav + content

These were direct children of the outer `<section className="space-y-6">`. After the new opening `<div className="space-y-6">`, leave the existing `<ReservePanel ... />` through the tab nav block (lines 67-100) as-is. Close with `</div></PageContainer>` instead of `</section>`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/budget/BudgetPage.tsx
git commit -m "refactor(budget): use PageContainer/Header; drop inline tab nav"
```

---

## Task 13: Normalize `FinancesPage`

**Files:**
- Modify: `frontend/src/features/budget/FinancesPage.tsx`

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
```

- [ ] **Step 2: Replace lines 25-33** (outer `<section>` opening + header) with:

```tsx
  return (
    <PageContainer width="default">
      <PageHeader
        title={t("budget.finances.title")}
        subtitle={t("budget.finances.subtitle")}
      />
      <div className="space-y-4">
```

- [ ] **Step 3: Change the closing `</section>` at line 99** to `</div></PageContainer>`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/budget/FinancesPage.tsx
git commit -m "refactor(finances): use PageContainer/Header"
```

---

## Task 14: Normalize `RenofondPage`

**Files:**
- Modify: `frontend/src/features/renofond/RenofondPage.tsx`

Drop the inline back-to-budget link (sidebar now offers nav). Page header subtitle is `renofond.subtitle`.

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
```

- [ ] **Step 2: Remove the `Link` import** at line 19. Change:

```tsx
import { Link, useParams } from "react-router-dom";
```
to:
```tsx
import { useParams } from "react-router-dom";
```

- [ ] **Step 3: Replace lines 44-46** (the guard at the top of `RenofondPage`) with:

```tsx
  if (!id)
    return (
      <PageContainer width="wide">
        <p className="text-red-700">{t("common.error")}</p>
      </PageContainer>
    );
  return <RenofondPageInner objectId={id} />;
```

- [ ] **Step 4: Replace lines 53-65** (the loading/error branches in `RenofondPageInner`) with:

```tsx
  if (projection.isLoading || contributions.isLoading) {
    return (
      <PageContainer width="wide">
        <p className="text-slate-500">{t("common.loading")}</p>
      </PageContainer>
    );
  }
  if (projection.isError) {
    const msg =
      projection.error instanceof ApiError && projection.error.status === 403
        ? t("renofond.errors.forbidden")
        : t("renofond.errors.generic");
    return (
      <PageContainer width="wide">
        <p className="text-red-700">{msg}</p>
      </PageContainer>
    );
  }
  if (contributions.isError) {
    return (
      <PageContainer width="wide">
        <p className="text-red-700">{t("renofond.errors.generic")}</p>
      </PageContainer>
    );
  }
```

- [ ] **Step 5: Replace lines 70-85** (the outer `<section>` opening + header) with:

```tsx
  return (
    <PageContainer width="wide">
      <PageHeader title={t("renofond.title")} subtitle={t("renofond.subtitle")} />
      <div className="space-y-6">
```

- [ ] **Step 6: Change the closing `</section>` at line 126** to `</div></PageContainer>`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/renofond/RenofondPage.tsx
git commit -m "refactor(renofond): use PageContainer/Header; drop inline back link"
```

---

## Task 15: Normalize `ProjectsPage`

**Files:**
- Modify: `frontend/src/features/projects/ProjectsPage.tsx`

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { Drawer } from "@/components/Drawer";
```

- [ ] **Step 2: Remove `Link` import** at line 10 (only the row's `Link to={/projects/...}` uses it — that one stays; check before deleting). Actually keep it — `ProjectsPage.tsx:101` uses `<Link to={...}>` for the row. **Skip this step.**

- [ ] **Step 3: Replace lines 26-32** (the no-objectId guard) with:

```tsx
  if (!objectId) {
    return (
      <PageContainer width="default">
        <p className="text-red-700">{t("common.error")}</p>
      </PageContainer>
    );
  }
```

- [ ] **Step 4: Replace lines 48-62** (the outer `<section>` opening + header) with:

```tsx
  return (
    <PageContainer width="default">
      <PageHeader
        title={t("projects.title")}
        subtitle={t("projects.subtitle")}
        actions={
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
          >
            {t("projects.create")}
          </button>
        }
      />
```

- [ ] **Step 5: Change the closing `</section>` at line 133** to `</PageContainer>`.

- [ ] **Step 6: Delete the inline Drawer** at lines 136-166.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/projects/ProjectsPage.tsx
git commit -m "refactor(projects): use PageContainer/Header + shared Drawer"
```

---

## Task 16: Normalize `ProjectDetailPage`

**Files:**
- Modify: `frontend/src/features/projects/ProjectDetailPage.tsx`

Drop the inline "← back to list" nav (line 79-86) — breadcrumbs now handle it.

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
```

- [ ] **Step 2: Remove the `Link` import** at line 9 — only the back-nav used it. Change:

```tsx
import { Link, useNavigate, useParams } from "react-router-dom";
```
to:
```tsx
import { useNavigate, useParams } from "react-router-dom";
```

- [ ] **Step 3: Replace lines 36-49** (loading + error branches) with:

```tsx
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
```

- [ ] **Step 4: Replace lines 70-87** (outer `<section>` opening + header) with:

```tsx
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
```

- [ ] **Step 5: Change the closing `</section>` at line 170** to `</PageContainer>`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/projects/ProjectDetailPage.tsx
git commit -m "refactor(projects): use PageContainer/Header in detail page"
```

---

## Task 17: Normalize `LotsPage`

**Files:**
- Modify: `frontend/src/features/lots/LotsPage.tsx`

Same shape as ProjectsPage.

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { Drawer } from "@/components/Drawer";
```

- [ ] **Step 2: Replace lines 24-30** (no-objectId guard) with:

```tsx
  if (!objectId) {
    return (
      <PageContainer width="default">
        <p className="text-red-700">{t("common.error")}</p>
      </PageContainer>
    );
  }
```

- [ ] **Step 3: Replace lines 39-53** (outer `<section>` opening + header) with:

```tsx
  return (
    <PageContainer width="default">
      <PageHeader
        title={t("lots.title")}
        subtitle={t("lots.subtitle")}
        actions={
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
          >
            {t("lots.create")}
          </button>
        }
      />
```

- [ ] **Step 4: Change the closing `</section>` at line 128** to `</PageContainer>`.

- [ ] **Step 5: Delete the inline Drawer** at lines 131-161.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/lots/LotsPage.tsx
git commit -m "refactor(lots): use PageContainer/Header + shared Drawer"
```

---

## Task 18: Normalize `LotDetailPage`

**Files:**
- Modify: `frontend/src/features/lots/LotDetailPage.tsx`

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
```

- [ ] **Step 2: Remove the `Link` import** at line 10. Change:

```tsx
import { Link, useNavigate, useParams } from "react-router-dom";
```
to:
```tsx
import { useNavigate, useParams } from "react-router-dom";
```

- [ ] **Step 3: Replace lines 61-74** (loading + error branches) with:

```tsx
  if (lotQuery.isLoading || !lotId) {
    return (
      <PageContainer width="narrow">
        <p className="text-slate-500">{t("common.loading")}</p>
      </PageContainer>
    );
  }
  if (lotQuery.isError || !lotQuery.data) {
    return (
      <PageContainer width="narrow">
        <p className="text-red-700">{t("common.error")}</p>
      </PageContainer>
    );
  }
```

- [ ] **Step 4: Replace lines 104-122** (outer `<section>` opening + header) with:

```tsx
  return (
    <PageContainer width="narrow">
      <PageHeader
        title={lot.name}
        subtitle={
          <>
            {t(`lots.status.${lot.status}`)}
            {lot.tender_deadline &&
              ` · ${new Date(lot.tender_deadline).toLocaleDateString("de-CH")}`}
            {lot.archived_at && ` · ${t("lots.archived")}`}
          </>
        }
      />
```

- [ ] **Step 5: Change the closing `</section>` at line 271** to `</PageContainer>`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/lots/LotDetailPage.tsx
git commit -m "refactor(lots): use PageContainer/Header in detail page"
```

---

## Task 19: Normalize `SuppliersPage`

**Files:**
- Modify: `frontend/src/features/suppliers/SuppliersPage.tsx`

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
import { Drawer } from "@/components/Drawer";
```

- [ ] **Step 2: Replace lines 24-30** (no-objectId guard) with:

```tsx
  if (!objectId) {
    return (
      <PageContainer width="default">
        <p className="text-red-700">{t("common.error")}</p>
      </PageContainer>
    );
  }
```

- [ ] **Step 3: Replace lines 39-53** (outer `<section>` opening + header) with:

```tsx
  return (
    <PageContainer width="default">
      <PageHeader
        title={t("suppliers.title")}
        subtitle={t("suppliers.subtitle")}
        actions={
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white hover:bg-slate-700"
          >
            {t("suppliers.create")}
          </button>
        }
      />
```

- [ ] **Step 4: Change the closing `</section>` at line 124** to `</PageContainer>`.

- [ ] **Step 5: Delete the inline Drawer** at lines 127-157.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/suppliers/SuppliersPage.tsx
git commit -m "refactor(suppliers): use PageContainer/Header + shared Drawer"
```

---

## Task 20: Normalize `SupplierDetailPage`

**Files:**
- Modify: `frontend/src/features/suppliers/SupplierDetailPage.tsx`

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
```

- [ ] **Step 2: Remove the `Link` import** at line 9. Change:

```tsx
import { Link, useNavigate, useParams } from "react-router-dom";
```
to:
```tsx
import { useNavigate, useParams } from "react-router-dom";
```

- [ ] **Step 3: Replace lines 30-43** (loading + error branches) with:

```tsx
  if (supplierQuery.isLoading || !supplierId) {
    return (
      <PageContainer width="narrow">
        <p className="text-slate-500">{t("common.loading")}</p>
      </PageContainer>
    );
  }
  if (supplierQuery.isError || !supplierQuery.data) {
    return (
      <PageContainer width="narrow">
        <p className="text-red-700">{t("common.error")}</p>
      </PageContainer>
    );
  }
```

- [ ] **Step 4: Replace lines 69-85** (outer `<section>` opening + header) with:

```tsx
  return (
    <PageContainer width="narrow">
      <PageHeader
        title={supplier.name}
        subtitle={
          <>
            {supplier.contact_email ?? "—"}
            {supplier.archived_at && ` · ${t("suppliers.archived")}`}
          </>
        }
      />
```

- [ ] **Step 5: Change the closing `</section>` at line 123** to `</PageContainer>`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/suppliers/SupplierDetailPage.tsx
git commit -m "refactor(suppliers): use PageContainer/Header in detail page"
```

---

## Task 21: Normalize `AuditPage` (both modes)

**Files:**
- Modify: `frontend/src/features/audit/AuditPage.tsx`

- [ ] **Step 1: Add imports** alongside existing imports:

```tsx
import { PageContainer } from "@/components/PageContainer";
import { PageHeader } from "@/components/PageHeader";
```

- [ ] **Step 2: Remove the `Link` import** at line 14 — only the error-branch back link used it. Change:

```tsx
import { Link, useParams } from "react-router-dom";
```
to:
```tsx
import { useParams } from "react-router-dom";
```

- [ ] **Step 3: Replace lines 29** (the guard in `ObjectAuditPage`) with:

```tsx
  if (!id)
    return (
      <PageContainer width="default">
        <p className="text-red-700">{t("common.error")}</p>
      </PageContainer>
    );
```

- [ ] **Step 4: Replace lines 78-95** (loading + error branches in `AuditViewer`) with:

```tsx
  if (loading) {
    return (
      <PageContainer width="default">
        <p className="text-slate-600">{t("common.loading")}</p>
      </PageContainer>
    );
  }
  if (error) {
    return (
      <PageContainer width="default">
        <PageHeader title={title} />
        <p className="rounded border border-red-300 bg-red-50 p-3 text-red-800">
          {error}
        </p>
      </PageContainer>
    );
  }
```

- [ ] **Step 5: Replace lines 97-102** (outer `<section>` + header) with:

```tsx
  return (
    <PageContainer width="default">
      <PageHeader title={title} subtitle={t("audit.subtitle")} />
```

- [ ] **Step 6: Change the closing `</section>` at line 137** to `</PageContainer>`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/audit/AuditPage.tsx
git commit -m "refactor(audit): use PageContainer/Header; drop inline back link"
```

---

## Task 22: Adopt `apiErrorMessage` in feature API clients

**Files:**
- Modify: `frontend/src/features/objects/ObjectsListPage.tsx:25`
- Modify: `frontend/src/features/objects/ObjectCreatePage.tsx:61`
- Modify: `frontend/src/features/objects/ObjectDetailPage.tsx:30`
- Modify: `frontend/src/features/costs/CostsPage.tsx:47`
- Modify: `frontend/src/features/renofond/RenofondPage.tsx:341`

Each of these sites has the same pattern:
```tsx
e instanceof ApiError ? String(e.detail) : t("common.error")
```

This loses the nice "detail.detail" extraction that `apiErrorMessage` provides. Replace each call.

- [ ] **Step 1: For each file listed, replace the pattern**:

Replace:
```tsx
e instanceof ApiError ? String(e.detail) : t("common.error")
```
with:
```tsx
apiErrorMessage(e, t("common.error"))
```

Then add the import:
```tsx
import { apiErrorMessage } from "@/lib/apiError";
```

And remove the now-unused `ApiError` import if it's the only remaining consumer of `ApiError` in the file. In files where `ApiError` is still used elsewhere (e.g. `RenofondPage.tsx` uses it for the 403 check at line 58), keep the import.

- [ ] **Step 2: Run typecheck**

Run: `cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/
git commit -m "refactor(errors): adopt apiErrorMessage helper in error sites"
```

---

## Task 23: Run frontend tests

**Files:**
- None — verification only.

- [ ] **Step 1: Run vitest**

Run: `cd /Users/stefan/Code/reno-budget/frontend && npm test -- --run`
Expected: all tests pass. If a test asserts on page structure (e.g. expects the old `<section>` wrapper or the old inline tab nav), update the test to match the new structure or delete it if it tested chrome we just removed.

- [ ] **Step 2: Run typecheck**

Run: `cd /Users/stefan/Code/reno-budget/frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Run linter**

Run: `cd /Users/stefan/Code/reno-budget/frontend && npm run lint`
Expected: clean. Most likely warnings: unused imports of `Link` or `ApiError` removed earlier — fix by deleting.

- [ ] **Step 4: Commit any test fixups**

```bash
git add frontend/
git commit -m "test(frontend): update assertions for layout refactor"
```

---

## Task 24: Rebuild docker `web` image and smoke test

**Files:**
- None — build + manual verify.

- [ ] **Step 1: Rebuild the web image**

Run: `docker compose -f /Users/stefan/Code/reno-budget/deploy/docker-compose.yml build web`
Expected: build succeeds. If the build fails on TS errors, fix them (Task 23 should have caught them — re-run typecheck if surprised).

- [ ] **Step 2: Recreate the web container**

Run: `docker compose -f /Users/stefan/Code/reno-budget/deploy/docker-compose.yml up -d web`
Expected: container goes to `Up (healthy)` within ~30s. Verify with `docker compose -f /Users/stefan/Code/reno-budget/deploy/docker-compose.yml ps`.

- [ ] **Step 3: Smoke test in browser**

Open http://localhost:8080 in a browser. Log in. Verify:
- Sidebar is visible on left, with: Home, Objekte, Finanzen, (Admin-Audit if superuser)
- Breadcrumbs visible in header on every page
- User menu (initials avatar) in top-right, with language switcher + logout
- Navigate to Objekte → click an object → sidebar now shows the per-object section with Units / Kosten / Budget / Projekte / Lose / Lieferanten / Renofond / Audit
- Click each per-object link, verify breadcrumb updates correctly (Home › Objekte › <Name> › <Section>)
- Click into a Project / Lot / Supplier detail page, verify breadcrumb includes parent object name and the per-object sidebar section stays visible
- On mobile width (devtools narrow), verify hamburger toggle works
- The back-button in the header works on detail pages

- [ ] **Step 4: Document the smoke result**

If everything passes, proceed. If anything fails, note which page broke and fix it; rebuild image; retest.

---

## Task 25: Push branch and open PR

**Files:**
- None — git only.

- [ ] **Step 1: Create branch (if not already on one)**

Run: `cd /Users/stefan/Code/reno-budget && git checkout -b feat/gui-layout-wire-and-normalize`

If commits from earlier tasks were on `main`, this still works — branch is created at HEAD. If you'd rather not have them on main, run this BEFORE Task 1 instead.

- [ ] **Step 2: Verify branch state**

Run: `git log --oneline main..HEAD`
Expected: ~18 commits from the tasks above.

- [ ] **Step 3: Push**

Run: `git push -u origin feat/gui-layout-wire-and-normalize`

- [ ] **Step 4: Open PR**

Run via gh CLI:

```bash
gh pr create --title "feat(gui): wire AppLayout + normalize page headers" --body "$(cat <<'EOF'
## Summary
- Wire the previously orphaned `AppLayout` into the router via nested routes — every authenticated page now renders inside the sidebar + breadcrumb chrome.
- Extend `AppLayout`: sidebar links for Projekte / Lose / Lieferanten under the per-object section; breadcrumbs cover all current routes including detail pages.
- Normalize page headers across 14 pages — extracted `PageContainer`, `PageHeader`, and shared `Drawer` components. Drops duplicated wrapper / title / back-link / inline-tab-nav markup.
- Adopt the orphaned `lib/apiError.ts` helper in feature API clients.

Out of scope (PR 2): cross-object top-level Projects/Lots/Suppliers pages — those need new backend endpoints.

## Test plan
- [x] `npm test -- --run` passes
- [x] `npx tsc --noEmit` clean
- [x] `npm run lint` clean
- [x] Docker rebuild succeeds; container goes healthy
- [x] Manual smoke: sidebar + breadcrumbs visible on every authenticated page; per-object section appears on detail pages; mobile drawer toggle works; back-button works

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Return the PR URL**
