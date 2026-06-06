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
          <Route path="/anmelden" element={<LoginPage />} />
          <Route path="/invite/:token" element={<AcceptInvitePage />} />
          <Route path="/passwort-zuruecksetzen" element={<PasswordResetRequestPage />} />
          <Route path="/passwort-zuruecksetzen/:token" element={<PasswordResetConfirmPage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <HomePage />
              </RequireAuth>
            }
          />
          <Route
            path="/objekte"
            element={
              <RequireAuth>
                <ObjectsListPage />
              </RequireAuth>
            }
          />
          <Route
            path="/objekte/neu"
            element={
              <RequireAuth>
                <ObjectCreatePage />
              </RequireAuth>
            }
          />
          <Route
            path="/objekte/:id"
            element={
              <RequireAuth>
                <ObjectDetailPage />
              </RequireAuth>
            }
          />
          <Route
            path="/objekte/:objectId/kosten"
            element={
              <RequireAuth>
                <CostsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/objekte/:id/budget"
            element={
              <RequireAuth>
                <BudgetPage />
              </RequireAuth>
            }
          />
          <Route
            path="/finanzen"
            element={
              <RequireAuth>
                <FinancesPage />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </QueryClientProvider>
  );
}
