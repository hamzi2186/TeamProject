import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { authApi } from "../api/auth";

export function AuthPage({ mode = "login" }: { mode?: "login" | "register" | "verify" | "forgot" | "reset" }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(() => {
    if (mode === "verify" && searchParams.get("delivery") === "sent") {
      return "A 6-digit verification code has been sent to your email. Please check your inbox or spam folder.";
    }
    if (mode === "verify" && searchParams.get("delivery") === "failed") {
      return "Your account was created, but the verification email could not be delivered. Try resending it.";
    }
    if (mode === "reset") {
      return "If your account exists, a 6-digit password reset code has been sent to your email.";
    }
    if (mode === "login" && searchParams.get("verified") === "1") {
      return "Email verified successfully! You can now sign in.";
    }
    if (mode === "login" && searchParams.get("reset") === "1") {
      return "Password reset successfully! You can now sign in with your new password.";
    }
    return "";
  });
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "register") {
        const result = await authApi.register(email, password);
        const delivery = result.verification_email_sent ? "sent" : "failed";
        navigate(`/auth/verify-email?email=${encodeURIComponent(email)}&delivery=${delivery}`, { replace: true });
      } else if (mode === "verify") {
        await authApi.verify(email, code);
        navigate(`/auth/login?verified=1&email=${encodeURIComponent(email)}`, { replace: true });
      } else if (mode === "forgot") {
        const result = await authApi.forgot(email);
        setNotice(result.message || "Reset code sent to your email.");
        navigate(`/auth/reset-password?email=${encodeURIComponent(email)}`, { replace: true });
      } else if (mode === "reset") {
        const result = await authApi.reset(email, code, newPassword);
        navigate(`/auth/login?reset=1&email=${encodeURIComponent(email)}`, { replace: true });
      } else {
        const session = await authApi.login(email, password);
        sessionStorage.setItem("trex_access_token", session.access_token);
        navigate("/", { replace: true });
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  }

  async function resendVerification() {
    if (!email) {
      setError("Please enter your email address first.");
      return;
    }
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await authApi.resend(email);
      setNotice(result.message || "A new verification code has been sent to your email.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Verification email could not be sent.");
    } finally {
      setLoading(false);
    }
  }

  async function resendForgotCode() {
    if (!email) {
      setError("Please enter your email address first.");
      return;
    }
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await authApi.forgot(email);
      setNotice(result.message || "A new password reset code has been sent.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not send password reset code.");
    } finally {
      setLoading(false);
    }
  }

  const isRegister = mode === "register";
  const isVerify = mode === "verify";
  const isForgot = mode === "forgot";
  const isReset = mode === "reset";
  const isLogin = mode === "login";

  const title = isRegister
    ? "Create your account"
    : isVerify
      ? "Verify your email"
      : isForgot
        ? "Forgot your password?"
        : isReset
          ? "Reset your password"
          : "Welcome back";

  const subtitle = isRegister
    ? "Create an account to manage leads and calls."
    : isVerify
      ? "Enter the six-digit verification code sent to your email."
      : isForgot
        ? "Enter your email address to receive a 6-digit recovery code."
        : isReset
          ? "Enter your recovery code and choose a new password."
          : "Sign in to review leads and manage calls.";

  return (
    <main className="auth-shell">
      <section className="form-panel">
        <div className="auth-card">
          <p className="eyebrow">T Rex</p>
          <h1>{title}</h1>
          <p className="subtitle">{subtitle}</p>
          <form onSubmit={submit}>
            <label>
              Email address
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
                placeholder="name@example.com"
              />
            </label>

            {isVerify && (
              <label>
                Verification code (6 digits)
                <input
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={code}
                  onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                  required
                  placeholder="123456"
                />
              </label>
            )}

            {isReset && (
              <>
                <label>
                  Reset code (6 digits)
                  <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    value={code}
                    onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                    required
                    placeholder="123456"
                  />
                </label>
                <label>
                  New password
                  <input
                    type="password"
                    minLength={10}
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    required
                    placeholder="••••••••••"
                  />
                  <small className="field-hint">Must be at least 10 characters.</small>
                </label>
              </>
            )}

            {(isLogin || isRegister) && (
              <label>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>Password</span>
                  {isLogin && (
                    <Link
                      to={`/auth/forgot-password${email ? `?email=${encodeURIComponent(email)}` : ""}`}
                      style={{ fontSize: "0.85rem", color: "var(--accent, #3b82f6)", textDecoration: "none" }}
                    >
                      Forgot password?
                    </Link>
                  )}
                </div>
                <input
                  type="password"
                  minLength={isRegister ? 10 : undefined}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  placeholder="••••••••••"
                />
                {isRegister && <small className="field-hint">Use at least 10 characters.</small>}
              </label>
            )}

            {notice && <div className="notice" role="status">{notice}</div>}
            {error && (
              <div className="notice error" role="alert">
                <div>{error}</div>
                {isLogin && (
                  <div style={{ marginTop: "8px", fontSize: "0.85rem", borderTop: "1px solid rgba(239, 68, 68, 0.3)", paddingTop: "6px" }}>
                    {error.toLowerCase().includes("verify") ? (
                      <span>
                        Need to verify?{" "}
                        <Link
                          to={`/auth/verify-email${email ? `?email=${encodeURIComponent(email)}` : ""}`}
                          style={{ color: "#93c5fd", fontWeight: 600, textDecoration: "underline" }}
                        >
                          Verify your email &rarr;
                        </Link>
                      </span>
                    ) : (
                      <span>
                        Forgot your password?{" "}
                        <Link
                          to={`/auth/forgot-password${email ? `?email=${encodeURIComponent(email)}` : ""}`}
                          style={{ color: "#93c5fd", fontWeight: 600, textDecoration: "underline" }}
                        >
                          Reset your password here &rarr;
                        </Link>
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            <button className="primary" disabled={loading}>
              {loading
                ? "Please wait..."
                : isRegister
                  ? "Create account"
                  : isVerify
                    ? "Verify email"
                    : isForgot
                      ? "Send reset code"
                      : isReset
                        ? "Save new password"
                        : "Sign in"}
            </button>

            {isVerify && (
              <button
                className="ghost"
                type="button"
                disabled={loading || !email}
                onClick={resendVerification}
              >
                Resend verification code
              </button>
            )}

            {isReset && (
              <button
                className="ghost"
                type="button"
                disabled={loading || !email}
                onClick={resendForgotCode}
              >
                Resend reset code
              </button>
            )}
          </form>

          <div className="auth-links" style={{ display: "flex", flexDirection: "column", gap: "8px", marginTop: "16px" }}>
            {isRegister && (
              <p>Already have an account? <Link to="/auth/login">Sign in</Link></p>
            )}

            {isLogin && (
              <>
                <p>Need an account? <Link to="/auth/register">Create one</Link></p>
                <p style={{ fontSize: "0.85rem", color: "var(--text-muted, #94a3b8)" }}>
                  Have an unverified account?{" "}
                  <Link to={`/auth/verify-email${email ? `?email=${encodeURIComponent(email)}` : ""}`}>
                    Verify email
                  </Link>
                </p>
              </>
            )}

            {(isVerify || isForgot || isReset) && (
              <p>Return to <Link to="/auth/login">Sign in</Link></p>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
