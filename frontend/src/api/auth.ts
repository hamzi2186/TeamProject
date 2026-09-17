import { apiRequest } from "./client";

export type AuthUser = {
  id: string;
  email: string;
  role: string;
  email_verified_at: string | null;
};

type Session = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: AuthUser;
};

type RegistrationResult = {
  message: string;
  verification_email_sent: boolean;
};

export const authApi = {
  register: (email: string, password: string) =>
    apiRequest<RegistrationResult>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  verify: (email: string, code: string) =>
    apiRequest<{ message: string }>("/api/v1/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    }),
  resend: (email: string) =>
    apiRequest<{ message: string }>("/api/v1/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  login: (email: string, password: string) =>
    apiRequest<Session>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  forgot: (email: string) =>
    apiRequest<{ message: string }>("/api/v1/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  reset: (email: string, code: string, newPassword: string) =>
    apiRequest<{ message: string }>("/api/v1/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ email, code, new_password: newPassword }),
    }),
};
