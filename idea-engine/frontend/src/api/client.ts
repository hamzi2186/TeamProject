const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8006").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;

  constructor(message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiClient<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    let errorMsg = `Request failed with status ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.error?.message) {
        errorMsg = errJson.error.message;
      }
    } catch {
      // Fall back to the generic message
    }
    throw new ApiError(errorMsg, response.status);
  }

  const json = await response.json();
  if (json.success === false) {
    throw new ApiError(json.error?.message || "The request could not be completed.", 400);
  }

  return json.data as T;
}

export function getDownloadUrl(reportId: string): string {
  return `${API_BASE_URL}/idea/reports/${reportId}/download`;
}