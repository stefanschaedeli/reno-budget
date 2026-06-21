import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import i18n from "@/i18n/i18n";
import { useAuth } from "@/features/auth/AuthContext";
import { getObject } from "@/features/objects/api";
import { fetchProject } from "@/features/projects/api";
import { fetchLot } from "@/features/lots/api";
import { fetchSupplier } from "@/features/suppliers/api";

interface Crumb {
  label: string;
  to?: string;
}

function useCurrentObjectId(): string | null {
  const { pathname } = useLocation();
  const m = pathname.match(/^\/objekte\/([^/]+)(?:\/|$)/);
  if (!m) return null;
  const id = m[1]!;
  if (id === "neu") return null;
  return id;
}

const DETAIL_ID_PATTERNS = {
  projects: /^\/projekte\/([^/]+)/,
  lose: /^\/lose\/([^/]+)(?:\/|$)/,
  lieferanten: /^\/lieferanten\/([^/]+)(?:\/|$)/,
} as const;

function useCurrentDetailId(prefix: keyof typeof DETAIL_ID_PATTERNS): string | null {
  const { pathname } = useLocation();
  // eslint-disable-next-line security/detect-object-injection -- prefix is a string-literal union
  const m = pathname.match(DETAIL_ID_PATTERNS[prefix]);
  return m ? m[1]! : null;
}

function useObjectName(id: string | null): string | undefined {
  const q = useQuery({
    queryKey: ["object-name", id],
    queryFn: () => getObject(id as string),
    enabled: !!id,
    staleTime: 60_000,
  });
  return q.data?.name;
}

function useNamedEntity<T extends { name: string; object_id: string }>(
  keyPrefix: string,
  id: string | null,
  fetcher: (id: string) => Promise<T>,
): { name: string | undefined; objectId: string | undefined } {
  const q = useQuery({
    queryKey: [keyPrefix, id],
    queryFn: () => fetcher(id as string),
    enabled: !!id,
    staleTime: 60_000,
  });
  // Return primitives so the consuming useMemo deps are stable across renders.
  return { name: q.data?.name, objectId: q.data?.object_id };
}

interface BreadcrumbInputs {
  objectName: string | undefined;
  projectName: string | undefined;
  projectParentObjectId: string | undefined;
  lotName: string | undefined;
  lotParentObjectId: string | undefined;
  supplierName: string | undefined;
  supplierParentObjectId: string | undefined;
}

function useBreadcrumbs(inputs: BreadcrumbInputs): Crumb[] {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const {
    objectName,
    projectName,
    projectParentObjectId,
    lotName,
    lotParentObjectId,
    supplierName,
    supplierParentObjectId,
  } = inputs;
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
        else if (tail === "lose") crumbs.push({ label: t("nav.crumb.lots") });
        else if (tail === "lieferanten") crumbs.push({ label: t("nav.crumb.suppliers") });
      }
    } else if (parts[0] === "projekte" && parts[1]) {
      if (projectParentObjectId) {
        crumbs.push({ label: t("nav.crumb.objects"), to: "/objekte" });
        crumbs.push({ label: "…", to: `/objekte/${projectParentObjectId}` });
      } else {
        crumbs.push({ label: t("nav.crumb.projects") });
      }
      crumbs.push({ label: projectName ?? "…" });
    } else if (parts[0] === "lose" && parts[1]) {
      if (lotParentObjectId) {
        crumbs.push({ label: t("nav.crumb.objects"), to: "/objekte" });
        crumbs.push({ label: "…", to: `/objekte/${lotParentObjectId}` });
        crumbs.push({
          label: t("nav.crumb.lots"),
          to: `/objekte/${lotParentObjectId}/lose`,
        });
      } else {
        crumbs.push({ label: t("nav.crumb.lots") });
      }
      crumbs.push({ label: lotName ?? "…" });
    } else if (parts[0] === "lieferanten" && parts[1]) {
      if (supplierParentObjectId) {
        crumbs.push({ label: t("nav.crumb.objects"), to: "/objekte" });
        crumbs.push({ label: "…", to: `/objekte/${supplierParentObjectId}` });
        crumbs.push({
          label: t("nav.crumb.suppliers"),
          to: `/objekte/${supplierParentObjectId}/lieferanten`,
        });
      } else {
        crumbs.push({ label: t("nav.crumb.suppliers") });
      }
      crumbs.push({ label: supplierName ?? "…" });
    } else if (parts[0] === "projekte" && !parts[1]) {
      crumbs.push({ label: t("nav.crumb.projektsListe") });
    } else if (parts[0] === "lose-uebersicht") {
      crumbs.push({ label: t("nav.crumb.lotsListe") });
    } else if (parts[0] === "lieferanten-uebersicht") {
      crumbs.push({ label: t("nav.crumb.suppliersListe") });
    } else if (parts[0] === "finanzen") {
      crumbs.push({ label: t("nav.crumb.finances") });
    } else if (parts[0] === "admin") {
      crumbs.push({ label: t("nav.crumb.admin") });
      if (parts[1] === "audit") crumbs.push({ label: t("nav.crumb.adminAudit") });
    }
    // Mark the last crumb as non-navigable (current page).
    const last = crumbs[crumbs.length - 1];
    if (last) delete last.to;
    return crumbs;
  }, [
    pathname,
    objectName,
    projectName,
    projectParentObjectId,
    lotName,
    lotParentObjectId,
    supplierName,
    supplierParentObjectId,
    t,
  ]);
}

function SidebarLink({
  to,
  end = false,
  icon,
  children,
  onNavigate,
}: {
  to: string;
  end?: boolean;
  icon: string;
  children: ReactNode;
  onNavigate?: (() => void) | undefined;
}): JSX.Element {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onNavigate}
      className={({ isActive }) =>
        `group relative flex items-center gap-3 px-3 py-2 text-sm transition ${
          isActive
            ? "text-ink"
            : "text-ink-muted hover:text-ink hover:bg-paper-sunk"
        }`
      }
    >
      {({ isActive }) => (
        <>
          <span
            aria-hidden
            className={`absolute left-0 top-1/2 h-5 -translate-y-1/2 transition-all ${
              isActive ? "w-[3px] bg-accent" : "w-0 bg-transparent"
            }`}
          />
          <span aria-hidden className="w-5 text-base leading-none">
            {icon}
          </span>
          <span className="truncate">{children}</span>
        </>
      )}
    </NavLink>
  );
}

function ObjectContextSection({
  objectId,
  objectName,
  onNavigate,
}: {
  objectId: string;
  objectName: string | undefined;
  onNavigate?: (() => void) | undefined;
}): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="mt-6 border-t border-rule pt-4">
      <p className="px-3 text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-ink-subtle">
        {t("nav.currentObject")}
      </p>
      <p className="mb-2 truncate px-3 py-1 font-display text-base text-ink">
        {objectName ?? "…"}
      </p>
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
    </div>
  );
}

function OverviewsSection({
  onNavigate,
}: {
  onNavigate?: (() => void) | undefined;
}): JSX.Element {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const containsOverview =
    pathname === "/projekte" ||
    pathname.startsWith("/lose-uebersicht") ||
    pathname.startsWith("/lieferanten-uebersicht");
  const [open, setOpen] = useState(containsOverview);
  return (
    <div className="mt-6 border-t border-rule pt-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-ink-subtle hover:text-ink"
        aria-expanded={open}
      >
        <span>{t("nav.overviews")}</span>
        <span aria-hidden className="text-ink-subtle">
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open && (
        <div className="mt-2 space-y-1">
          <SidebarLink to="/projekte" icon="🗂️" onNavigate={onNavigate}>
            {t("nav.projektsListe")}
          </SidebarLink>
          <SidebarLink to="/lose-uebersicht" icon="📦" onNavigate={onNavigate}>
            {t("nav.lotsListe")}
          </SidebarLink>
          <SidebarLink
            to="/lieferanten-uebersicht"
            icon="🤝"
            onNavigate={onNavigate}
          >
            {t("nav.suppliersListe")}
          </SidebarLink>
        </div>
      )}
    </div>
  );
}

function UserMenu(): JSX.Element {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState<string>(i18n.language);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-user-menu]")) setOpen(false);
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, []);

  const initials = (user?.display_name ?? "?")
    .split(/\s+/)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .slice(0, 2)
    .join("");

  return (
    <div className="relative" data-user-menu>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("nav.userMenu")}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-full border border-rule bg-paper-raised px-2 py-1 text-sm hover:bg-paper-sunk"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-ink text-xs font-semibold text-paper">
          {initials || "👤"}
        </span>
        <span className="hidden max-w-[10rem] truncate sm:inline">
          {user?.display_name}
        </span>
        <span aria-hidden className="text-ink-subtle">
          ▾
        </span>
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-56 rounded-sheet border border-rule bg-paper-raised p-1 shadow-panel"
        >
          {user && (
            <div className="border-b border-rule px-3 py-2 text-xs text-ink-muted">
              {user.email}
            </div>
          )}
          <div className="flex items-center justify-between px-3 py-2 text-sm">
            <span className="text-ink-muted">{t("nav.language")}</span>
            <div className="flex gap-1">
              {(["de", "en"] as const).map((code) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => {
                    void i18n.changeLanguage(code);
                    setLang(code);
                  }}
                  className={`rounded-sheet px-2 py-0.5 text-xs ${
                    lang === code
                      ? "bg-ink text-paper"
                      : "text-ink-muted hover:bg-paper-sunk hover:text-ink"
                  }`}
                >
                  {code.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => void logout()}
            className="w-full rounded-sheet px-3 py-2 text-left text-sm text-ink-muted hover:bg-paper-sunk hover:text-ink"
          >
            {t("auth.logout")}
          </button>
        </div>
      )}
    </div>
  );
}

function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }): JSX.Element {
  return (
    <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
      <ol className="flex flex-wrap items-center gap-1 text-sm text-ink-muted">
        {crumbs.map((c, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <li key={i} className="flex items-center gap-1">
              {i > 0 && (
                <span aria-hidden className="text-ink-subtle">
                  ›
                </span>
              )}
              {c.to && !isLast ? (
                <Link
                  to={c.to}
                  className="rounded-sheet px-1 hover:text-accent"
                >
                  {c.label}
                </Link>
              ) : (
                <span
                  aria-current={isLast ? "page" : undefined}
                  className={isLast ? "font-medium text-ink" : ""}
                >
                  {c.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export function AppLayout(): JSX.Element {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const params = useParams();
  const objectId = useCurrentObjectId();
  const objectName = useObjectName(objectId);
  const projectId = useCurrentDetailId("projects");
  const { name: projectName, objectId: projectParentObjectId } =
    useNamedEntity("project-name", projectId, fetchProject);
  const lotId = useCurrentDetailId("lose");
  const { name: lotName, objectId: lotParentObjectId } =
    useNamedEntity("lot-name", lotId, fetchLot);
  const supplierId = useCurrentDetailId("lieferanten");
  const { name: supplierName, objectId: supplierParentObjectId } =
    useNamedEntity("supplier-name", supplierId, fetchSupplier);

  // Effective object id: own /objekte/:id route OR derived from a detail page's parent.
  const effectiveObjectId =
    objectId ?? projectParentObjectId ?? lotParentObjectId ?? supplierParentObjectId ?? null;
  const effectiveObjectName = objectName;

  const crumbs = useBreadcrumbs({
    objectName,
    projectName,
    projectParentObjectId,
    lotName,
    lotParentObjectId,
    supplierName,
    supplierParentObjectId,
  });

  // Drawer state for mobile.
  const [drawerOpen, setDrawerOpen] = useState(false);
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  const canGoBack = crumbs.length > 1;
  const onBack = () => {
    // Prefer history; fall back to parent crumb if history is empty.
    if (window.history.length > 1) navigate(-1);
    else {
      const parent = [...crumbs].reverse().find((c) => c.to);
      if (parent?.to) navigate(parent.to);
    }
  };

  // Suppress unused-var warning; `params` kept for future per-route extensions.
  void params;

  return (
    <div className="min-h-screen bg-paper text-ink">
      {/* Mobile drawer backdrop */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-30 bg-ink/40 md:hidden"
          onClick={() => setDrawerOpen(false)}
          aria-hidden
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-rule bg-paper transition-transform md:translate-x-0 ${
          drawerOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="flex items-center justify-between border-b border-rule px-4 py-5">
          <Link to="/" className="flex items-baseline gap-2">
            <span
              aria-hidden
              className="font-display text-2xl font-semibold leading-none text-ink"
              style={{ fontVariationSettings: '"SOFT" 30, "WONK" 1' }}
            >
              Reno
            </span>
            <span className="font-display text-2xl leading-none text-accent">
              ·
            </span>
            <span className="font-display text-2xl font-light italic leading-none text-ink-muted">
              budget
            </span>
            <span className="sr-only">{t("app.title")}</span>
          </Link>
          <button
            type="button"
            onClick={() => setDrawerOpen(false)}
            className="rounded-sheet p-1 text-ink-subtle hover:bg-paper-sunk hover:text-ink md:hidden"
            aria-label={t("nav.closeMenu")}
          >
            ✕
          </button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          <SidebarLink to="/" end icon="🏠" onNavigate={() => setDrawerOpen(false)}>
            {t("nav.home")}
          </SidebarLink>
          <SidebarLink
            to="/objekte"
            icon="🏢"
            onNavigate={() => setDrawerOpen(false)}
          >
            {t("nav.objects")}
          </SidebarLink>
          <SidebarLink
            to="/finanzen"
            icon="💰"
            onNavigate={() => setDrawerOpen(false)}
          >
            {t("nav.finances")}
          </SidebarLink>
          {user?.is_superuser && (
            <SidebarLink
              to="/admin/audit"
              icon="📋"
              onNavigate={() => setDrawerOpen(false)}
            >
              {t("nav.adminAudit")}
            </SidebarLink>
          )}

          {effectiveObjectId && (
            <ObjectContextSection
              objectId={effectiveObjectId}
              objectName={effectiveObjectName}
              onNavigate={() => setDrawerOpen(false)}
            />
          )}

          <OverviewsSection onNavigate={() => setDrawerOpen(false)} />
        </nav>
        <div className="border-t border-rule px-4 py-3 text-[0.65rem] uppercase tracking-[0.18em] text-ink-subtle">
          {t("app.title")}
        </div>
      </aside>

      {/* Main column */}
      <div className="md:pl-64">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-rule bg-paper/95 px-4 py-3 backdrop-blur">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="rounded-sheet p-2 text-ink-muted hover:bg-paper-sunk hover:text-ink md:hidden"
            aria-label={t("nav.openMenu")}
          >
            ☰
          </button>
          <button
            type="button"
            onClick={onBack}
            disabled={!canGoBack}
            className="flex items-center gap-1 rounded-sheet border border-rule px-2 py-1 text-sm text-ink-muted hover:border-ink/30 hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
            aria-label={t("nav.back")}
          >
            <span aria-hidden>‹</span>
            <span className="hidden sm:inline">{t("nav.back")}</span>
          </button>
          <Breadcrumbs crumbs={crumbs} />
          <UserMenu />
        </header>
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
