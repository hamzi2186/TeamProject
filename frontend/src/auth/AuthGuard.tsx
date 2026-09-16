import { type ReactNode, useEffect } from "react";
import { isAuthenticated } from "./auth";

const ROOT_AUTH_URL = import.meta.env.VITE_ROOT_AUTH_URL ?? "http://localhost:5173/auth/login";

/**
 * AuthGuard redirects to the shared root auth service if no valid token exists.
 * The root platform (feat/foundation-auth-docker) owns auth — this engine is a consumer.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  useEffect(() => {
    if (!isAuthenticated()) {
      window.location.href = ROOT_AUTH_URL;
    }
  }, []);

  if (!isAuthenticated()) {
    return (
      <div className="auth-redirect">
        <p>Redirecting to sign in…</p>
      </div>
    );
  }

  return <>{children}</>;
}
