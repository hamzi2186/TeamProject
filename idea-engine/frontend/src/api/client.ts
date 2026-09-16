const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8006";

export async function apiClient<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMsg = `HTTP Error ${response.status}`;
    try {
      const errJson = await response.json();
      if (errJson.error?.message) {
        errorMsg = errJson.error.message;
      }
    } catch {
      // Ignore json parse error
    }
    throw new Error(errorMsg);
  }

  const json = await response.json();
  if (json.success === false) {
    throw new Error(json.error?.message || "API request failed");
  }

  return json.data as T;
}

export function getDownloadUrl(reportId: string): string {
  return `${API_BASE_URL}/idea/reports/${reportId}/download`;
}
