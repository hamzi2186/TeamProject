import { authFetch } from "./client";

export interface AuthUser {
  id: string;
  email: string;
  role: string;
  email_verified_at: string | null;
}

export interface Session {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: AuthUser;
}

export const authApi = {
  register: (email: string, password: string) =>
    authFetch<{ message: string }>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  verify: (email: string, code: string) =>
    authFetch<{ message: string }>("/api/v1/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    }),

  resend: (email: string) =>
    authFetch<{ message: string }>("/api/v1/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  login: (email: string, password: string) =>
    authFetch<Session>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  refresh: (refreshToken: string) =>
    authFetch<Session>("/api/v1/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),

  logout: (refreshToken?: string) =>
    authFetch<void>("/api/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken ?? null }),
    }),

  me: () =>
    authFetch<AuthUser>("/api/v1/auth/me"),

  forgot: (email: string) =>
    authFetch<{ message: string }>("/api/v1/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  reset: (email: string, code: string, newPassword: string) =>
    authFetch<{ message: string }>("/api/v1/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ email, code, new_password: newPassword }),
    }),
};
