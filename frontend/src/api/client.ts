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
    throw new ApiError(body.detail ?? body.error ?? "Request failed.", response.status);
  }

  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}
