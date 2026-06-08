import { useTranslation } from "react-i18next";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "@/features/auth/AuthContext";
import { LoginPage } from "@/features/auth/LoginPage";
import { AcceptInvitePage } from "@/features/auth/AcceptInvitePage";
import { PasswordResetRequestPage } from "@/features/auth/PasswordResetRequestPage";
import { PasswordResetConfirmPage } from "@/features/auth/PasswordResetConfirmPage";
import { HomePage } from "@/features/auth/HomePage";
import { ObjectsListPage } from "@/features/objects/ObjectsListPage";
import { ObjectCreatePage } from "@/features/objects/ObjectCreatePage";
import { ObjectDetailPage } from "@/features/objects/ObjectDetailPage";
import { CostsPage } from "@/features/costs/CostsPage";
import { BudgetPage } from "@/features/budget/BudgetPage";
import { FinancesPage } from "@/features/budget/FinancesPage";
import { RenofondPage } from "@/features/renofond/RenofondPage";
import { GlobalAuditPage, ObjectAuditPage } from "@/features/audit/AuditPage";
import { ProjectsPage } from "@/features/projects/ProjectsPage";
import { ProjectDetailPage } from "@/features/projects/ProjectDetailPage";
import { AllProjectsPage } from "@/features/projects/AllProjectsPage";
import { LotsPage } from "@/features/lots/LotsPage";
import { LotDetailPage } from "@/features/lots/LotDetailPage";
import { AllLotsPage } from "@/features/lots/AllLotsPage";
import { SuppliersPage } from "@/features/suppliers/SuppliersPage";
import { SupplierDetailPage } from "@/features/suppliers/SupplierDetailPage";
import { AllSuppliersPage } from "@/features/suppliers/AllSuppliersPage";
import { AppLayout } from "@/components/AppLayout";

/**
 * Single QueryClient for the whole app. Defaults are conservative:
 * one retry on transient failures, no automatic refetch on window focus
 * (the user mostly works inside one tab; aggressive refetch surprises
 * mid-edit).
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function RequireAuth({ children }: { children: React.ReactElement }) {
  const { user, bootstrapping } = useAuth();
  const { t } = useTranslation();
  if (bootstrapping) {
    return (
      <p className="mx-auto mt-16 max-w-md text-center text-slate-500">{t("common.loading")}</p>
    );
  }
  if (!user) return <Navigate to="/anmelden" replace />;
  return children;
}

export function App(): JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
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
              <Route path="/projekte" element={<AllProjectsPage />} />
              <Route path="/lose-uebersicht" element={<AllLotsPage />} />
              <Route path="/lieferanten-uebersicht" element={<AllSuppliersPage />} />
              <Route path="/objekte/:objectId/projekte" element={<ProjectsPage />} />
              <Route path="/projekte/:projectId" element={<ProjectDetailPage />} />
              <Route path="/objekte/:objectId/lose" element={<LotsPage />} />
              <Route path="/lose/:lotId" element={<LotDetailPage />} />
              <Route path="/objekte/:objectId/lieferanten" element={<SuppliersPage />} />
              <Route path="/lieferanten/:supplierId" element={<SupplierDetailPage />} />
              <Route path="/objekte/:id/audit" element={<ObjectAuditPage />} />
              <Route path="/admin/audit" element={<GlobalAuditPage />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
      </BrowserRouter>
    </AuthProvider>
    </QueryClientProvider>
  );
}
