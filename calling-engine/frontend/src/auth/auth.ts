/**
 * Auth token utilities.
 * Access token  → sessionStorage  (cleared on tab close)
 * Refresh token → localStorage    (persists across tabs)
 */

const ACCESS_KEY  = "trex_access_token";
const REFRESH_KEY = "trex_refresh_token";

/* ── Access token ─────────────────────────────────────────────────────── */
export function getToken(): string | null {
  return sessionStorage.getItem(ACCESS_KEY);
}
export function setToken(token: string): void {
  sessionStorage.setItem(ACCESS_KEY, token);
}
export function clearToken(): void {
  sessionStorage.removeItem(ACCESS_KEY);
}

/* ── Refresh token ────────────────────────────────────────────────────── */
export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}
export function setRefreshToken(token: string): void {
  localStorage.setItem(REFRESH_KEY, token);
}
export function clearRefreshToken(): void {
  localStorage.removeItem(REFRESH_KEY);
}

/* ── Session helpers ──────────────────────────────────────────────────── */
export function saveSession(accessToken: string, refreshToken: string): void {
  setToken(accessToken);
  setRefreshToken(refreshToken);
}

export function clearSession(): void {
  clearToken();
  clearRefreshToken();
}

/* ── Token inspection (no signature verify — server does that) ────────── */
function parsePayload(token: string): Record<string, unknown> | null {
  try {
    const [, b64] = token.split(".");
    return JSON.parse(atob(b64.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return null;
  }
}

export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;
  const payload = parsePayload(token);
  if (!payload) return false;
  return typeof payload.exp === "number" && payload.exp * 1000 > Date.now();
}

export function getUserFromToken(): { userId: string; role: string; email: string } | null {
  const token = getToken();
  if (!token) return null;
  const payload = parsePayload(token);
  if (!payload) return null;
  return {
    userId: String(payload.sub ?? ""),
    role:   String(payload.role ?? "customer"),
    email:  String(payload.email ?? ""),
  };
}
