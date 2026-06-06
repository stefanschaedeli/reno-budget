import { useTranslation } from "react-i18next";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/features/auth/AuthContext";
import { LoginPage } from "@/features/auth/LoginPage";
import { AcceptInvitePage } from "@/features/auth/AcceptInvitePage";
import { PasswordResetRequestPage } from "@/features/auth/PasswordResetRequestPage";
import { PasswordResetConfirmPage } from "@/features/auth/PasswordResetConfirmPage";
import { HomePage } from "@/features/auth/HomePage";

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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
