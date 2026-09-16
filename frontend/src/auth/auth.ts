/**
 * Auth utilities — reads JWT access token issued by the shared root auth service.
 * The root platform (feat/foundation-auth-docker) issues tokens; this engine consumes them.
 */

const TOKEN_KEY = "trex_access_token";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  const token = getToken();
  if (!token) return false;
  try {
    // Quick expiry check without full verify (server will reject if actually expired)
    const [, payloadB64] = token.split(".");
    const payload = JSON.parse(atob(payloadB64.replace(/-/g, "+").replace(/_/g, "/")));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

export function getUserFromToken(): { userId: string; role: string; email: string } | null {
  const token = getToken();
  if (!token) return null;
  try {
    const [, payloadB64] = token.split(".");
    const payload = JSON.parse(atob(payloadB64.replace(/-/g, "+").replace(/_/g, "/")));
    return { userId: payload.sub, role: payload.role ?? "customer", email: payload.email ?? "" };
  } catch {
    return null;
  }
}
