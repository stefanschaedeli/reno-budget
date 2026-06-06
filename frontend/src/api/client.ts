/**
 * Thin fetch wrapper that handles:
 *  - JSON bodies
 *  - Bearer token attachment from the auth store
 *  - 401 → automatic refresh attempt → retry, then logout if refresh fails
 *  - CSRF header attachment for cookie-bearing endpoints
 *
 * Intentionally tiny; we don't pull in axios. Errors are thrown as
 * {@link ApiError} so React Query can surface them.
 */

const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
  }
}

type AccessTokenGetter = () => string | null;
type AccessTokenSetter = (token: string | null) => void;

let getAccessToken: AccessTokenGetter = () => null;
let setAccessToken: AccessTokenSetter = () => {};

export function wireTokenAccess(getter: AccessTokenGetter, setter: AccessTokenSetter): void {
  getAccessToken = getter;
  setAccessToken = setter;
}

function readCsrfCookie(): string {
  const m = document.cookie.match(/(?:^|;\s*)reno_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]!) : "";
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  json?: unknown;
  /** True for endpoints that use the refresh cookie + require CSRF. */
  withCsrf?: boolean;
  /** Whether to retry once after a refresh on 401. Default true. */
  retryOnUnauthorized?: boolean;
}

async function tryRefresh(): Promise<boolean> {
  const r = await fetch(`${API_PREFIX}/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: { "X-CSRF-Token": readCsrfCookie() },
  });
  if (!r.ok) {
    setAccessToken(null);
    return false;
  }
  const body = (await r.json()) as { access_token: string };
  setAccessToken(body.access_token);
  return true;
}

export async function apiRequest<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", json, withCsrf = false, retryOnUnauthorized = true } = opts;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (json !== undefined) headers["Content-Type"] = "application/json";
  const access = getAccessToken();
  if (access) headers["Authorization"] = `Bearer ${access}`;
  if (withCsrf) headers["X-CSRF-Token"] = readCsrfCookie();

  const url = path.startsWith("/api/") ? path : `${API_PREFIX}${path}`;

  const init: RequestInit = { method, headers, credentials: "include" };
  if (json !== undefined) init.body = JSON.stringify(json);
  const response = await fetch(url, init);

  if (response.status === 401 && retryOnUnauthorized && access) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      return apiRequest<T>(path, { ...opts, retryOnUnauthorized: false });
    }
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const body: unknown = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = (body as { detail?: unknown })?.detail ?? body;
    throw new ApiError(response.status, detail);
  }

  return body as T;
}
