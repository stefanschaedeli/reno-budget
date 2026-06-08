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

function useCurrentDetailId(prefix: "projects" | "lose" | "lieferanten"): string | null {
  const { pathname } = useLocation();
  const m = pathname.match(new RegExp(`^/${prefix}/([^/]+)(?:/|$)`));
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

function useProjectName(id: string | null): { name: string | undefined; objectId: string | undefined } {
  const q = useQuery({
    queryKey: ["project-name", id],
    queryFn: () => fetchProject(id as string),
    enabled: !!id,
    staleTime: 60_000,
  });
  return { name: q.data?.name, objectId: q.data?.object_id };
}

function useLotName(id: string | null): { name: string | undefined; objectId: string | undefined } {
  const q = useQuery({
    queryKey: ["lot-name", id],
    queryFn: () => fetchLot(id as string),
    enabled: !!id,
    staleTime: 60_000,
  });
  return { name: q.data?.name, objectId: q.data?.object_id };
}

function useSupplierName(id: string | null): { name: string | undefined; objectId: string | undefined } {
  const q = useQuery({
    queryKey: ["supplier-name", id],
    queryFn: () => fetchSupplier(id as string),
    enabled: !!id,
    staleTime: 60_000,
  });
  return { name: q.data?.name, objectId: q.data?.object_id };
}

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
        `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition ${
          isActive
            ? "bg-slate-900 text-white"
            : "text-slate-700 hover:bg-slate-100"
        }`
      }
    >
      <span aria-hidden className="w-5 text-base leading-none">
        {icon}
      </span>
      <span className="truncate">{children}</span>
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
    <div className="mt-6 border-t border-slate-200 pt-4">
      <p className="px-3 text-xs font-semibold uppercase tracking-wider text-slate-400">
        {t("nav.currentObject")}
      </p>
      <p className="mb-2 truncate px-3 py-1 text-sm font-medium text-slate-900">
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
        className="flex items-center gap-2 rounded-full border border-slate-300 bg-white px-2 py-1 text-sm hover:bg-slate-50"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
          {initials || "👤"}
        </span>
        <span className="hidden max-w-[10rem] truncate sm:inline">
          {user?.display_name}
        </span>
        <span aria-hidden className="text-slate-400">
          ▾
        </span>
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-56 rounded-md border border-slate-200 bg-white p-1 shadow-lg"
        >
          {user && (
            <div className="border-b border-slate-100 px-3 py-2 text-xs text-slate-500">
              {user.email}
            </div>
          )}
          <div className="flex items-center justify-between px-3 py-2 text-sm">
            <span className="text-slate-600">{t("nav.language")}</span>
            <div className="flex gap-1">
              {(["de", "en"] as const).map((code) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => {
                    void i18n.changeLanguage(code);
                    setLang(code);
                  }}
                  className={`rounded px-2 py-0.5 text-xs ${
                    lang === code
                      ? "bg-slate-900 text-white"
                      : "text-slate-600 hover:bg-slate-100"
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
            className="w-full rounded px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
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
      <ol className="flex flex-wrap items-center gap-1 text-sm text-slate-500">
        {crumbs.map((c, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <li key={i} className="flex items-center gap-1">
              {i > 0 && (
                <span aria-hidden className="text-slate-300">
                  ›
                </span>
              )}
              {c.to && !isLast ? (
                <Link
                  to={c.to}
                  className="rounded px-1 hover:bg-slate-100 hover:text-slate-900"
                >
                  {c.label}
                </Link>
              ) : (
                <span
                  aria-current={isLast ? "page" : undefined}
                  className={isLast ? "font-medium text-slate-900" : ""}
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
  const projectInfo = useProjectName(projectId);
  const lotId = useCurrentDetailId("lose");
  const lotInfo = useLotName(lotId);
  const supplierId = useCurrentDetailId("lieferanten");
  const supplierInfo = useSupplierName(supplierId);

  // Effective object id: own /objekte/:id route OR derived from a detail page's parent.
  const effectiveObjectId =
    objectId ?? projectInfo.objectId ?? lotInfo.objectId ?? supplierInfo.objectId ?? null;
  const effectiveObjectName = objectName;

  const crumbs = useBreadcrumbs(objectName, projectInfo, lotInfo, supplierInfo);

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
  // `effectiveObjectId` / `effectiveObjectName` are wired up in the next task.
  void params;
  void effectiveObjectId;
  void effectiveObjectName;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Mobile drawer backdrop */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40 md:hidden"
          onClick={() => setDrawerOpen(false)}
          aria-hidden
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform md:translate-x-0 ${
          drawerOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-4">
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-slate-900 text-sm font-bold text-white">
              R
            </span>
            <span className="text-base font-semibold">{t("app.title")}</span>
          </Link>
          <button
            type="button"
            onClick={() => setDrawerOpen(false)}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 md:hidden"
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

          {objectId && (
            <ObjectContextSection
              objectId={objectId}
              objectName={objectName}
              onNavigate={() => setDrawerOpen(false)}
            />
          )}
        </nav>
        <div className="border-t border-slate-200 px-4 py-3 text-xs text-slate-400">
          {t("app.title")}
        </div>
      </aside>

      {/* Main column */}
      <div className="md:pl-64">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="rounded p-2 text-slate-600 hover:bg-slate-100 md:hidden"
            aria-label={t("nav.openMenu")}
          >
            ☰
          </button>
          <button
            type="button"
            onClick={onBack}
            disabled={!canGoBack}
            className="flex items-center gap-1 rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-600 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
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
