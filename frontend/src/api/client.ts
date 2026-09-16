import { getToken } from "../auth/auth";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8002";

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
    return value.map((item) => readableError(item)).filter(Boolean).join(" ") || "Request failed.";
  }
  if (value && typeof value === "object") {
    const item = value as Record<string, unknown>;
    if (typeof item.msg === "string") return item.msg;
    if (typeof item.message === "string") return item.message;
    if (typeof item.detail === "string") return item.detail;
    return Object.values(item).map((entry) => readableError(entry)).filter(Boolean).join(" ") || "Request failed.";
  }
  return "Request failed.";
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(readableError(body.detail ?? body.error ?? "Request failed."), response.status);
  }

  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}

export const apiRequest = apiFetch;
