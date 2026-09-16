import { type ReactNode, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { isAuthenticated } from "./auth";

/**
 * Protects a route — redirects to the calling engine's own login page
 * if no valid access token exists in sessionStorage.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const navigate = useNavigate();

  useEffect(() => {
    if (!isAuthenticated()) {
      navigate("/auth/login", { replace: true });
    }
  }, [navigate]);

  if (!isAuthenticated()) {
    return (
      <div className="auth-redirect">
        <p>Redirecting…</p>
      </div>
    );
  }

  return <>{children}</>;
}
