import { getToken } from "../auth/auth";

/**
 * Two base URLs:
 *  - AUTH_BASE  → root platform backend (port 8000) — issues JWT tokens
 *  - API_BASE   → calling engine backend (port 8002) — call data
 *
 * In production (Docker) these are injected via VITE_ env vars.
 * In dev Vite proxies both /api/v1/auth and /api/v1/calling, so we use "".
 */
const AUTH_BASE = import.meta.env.VITE_AUTH_BASE_URL ?? "";
const API_BASE  = import.meta.env.VITE_API_BASE_URL  ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function readableError(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value.map((v) => readableError(v)).filter(Boolean).join(" ") || "Request failed.";
  }
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    if (typeof obj.msg     === "string") return obj.msg;
    if (typeof obj.message === "string") return obj.message;
    if (typeof obj.detail  === "string") return obj.detail;
    return Object.values(obj).map((v) => readableError(v)).filter(Boolean).join(" ") || "Request failed.";
  }
  return "Request failed.";
}

async function fetchBase<T>(base: string, path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${base}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      readableError(body.detail ?? body.error ?? "Request failed."),
      res.status,
    );
  }

  return res.status === 204 ? (undefined as T) : (res.json() as Promise<T>);
}

/** Calls the root platform backend — used for all /api/v1/auth/* routes */
export function authFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  return fetchBase<T>(AUTH_BASE, path, init);
}

/** Calls the calling engine backend — used for /api/v1/calling/* routes */
export function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  return fetchBase<T>(API_BASE, path, init);
}

// Legacy alias kept so existing calling.ts imports don't break
export const apiRequest = apiFetch;
