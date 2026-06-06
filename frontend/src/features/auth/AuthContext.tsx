import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { apiRequest, wireTokenAccess } from "@/api/client";
import type { CurrentUser, LoginRequest, TokenResponse } from "./types";

interface AuthState {
  user: CurrentUser | null;
  bootstrapping: boolean;
  login: (req: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  /** Called after the invitation-accept flow returns its TokenResponse. */
  hydrateFromToken: (token: string) => Promise<void>;
  accessToken: string | null;
}

const AuthCtx = createContext<AuthState | undefined>(undefined);

let _accessToken: string | null = null;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [bootstrapping, setBootstrapping] = useState(true);

  const updateAccessToken = useCallback((t: string | null) => {
    _accessToken = t;
    setAccessToken(t);
  }, []);

  // Wire the API client to read/write the access token through us.
  useEffect(() => {
    wireTokenAccess(
      () => _accessToken,
      (t) => updateAccessToken(t),
    );
  }, [updateAccessToken]);

  // On first mount, try a silent refresh; if successful, load /me.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await fetch("/api/v1/auth/refresh", {
          method: "POST",
          credentials: "include",
          headers: { "X-CSRF-Token": readCsrfCookie() },
        });
        if (r.ok) {
          const body = (await r.json()) as TokenResponse;
          if (!cancelled) updateAccessToken(body.access_token);
          const me = await apiRequest<CurrentUser>("/auth/me");
          if (!cancelled) setUser(me);
        }
      } catch {
        /* ignore — user is simply not logged in */
      } finally {
        if (!cancelled) setBootstrapping(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [updateAccessToken]);

  const login = useCallback(
    async (req: LoginRequest) => {
      const t = await apiRequest<TokenResponse>("/auth/login", { method: "POST", json: req });
      updateAccessToken(t.access_token);
      const me = await apiRequest<CurrentUser>("/auth/me");
      setUser(me);
    },
    [updateAccessToken],
  );

  const logout = useCallback(async () => {
    try {
      await apiRequest<void>("/auth/logout", { method: "POST", withCsrf: true });
    } catch {
      /* even if logout fails server-side, clear local state */
    }
    updateAccessToken(null);
    setUser(null);
  }, [updateAccessToken]);

  const hydrateFromToken = useCallback(
    async (token: string) => {
      updateAccessToken(token);
      const me = await apiRequest<CurrentUser>("/auth/me");
      setUser(me);
    },
    [updateAccessToken],
  );

  const value = useMemo<AuthState>(
    () => ({ user, bootstrapping, login, logout, hydrateFromToken, accessToken }),
    [user, bootstrapping, login, logout, hydrateFromToken, accessToken],
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

function readCsrfCookie(): string {
  const m = document.cookie.match(/(?:^|;\s*)reno_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]!) : "";
}
