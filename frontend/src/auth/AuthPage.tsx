import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { authApi } from "../api/auth";

export function AuthPage({ mode = "login" }: { mode?: "login" | "register" | "verify" | "forgot" | "reset" }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(
    mode === "verify" && searchParams.get("delivery") === "failed"
      ? "Your account was created, but the verification email could not be delivered. Try resending it."
      : "",
  );
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
      } else {
        const session = await authApi.login(email, password);
        sessionStorage.setItem("trex_access_token", session.access_token);
        navigate("/", { replace: true });
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign in failed.");
    } finally {
      setLoading(false);
    }
  }

  async function resendVerification() {
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await authApi.resend(email);
      setNotice(result.message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Verification email could not be sent.");
    } finally {
      setLoading(false);
    }
  }

  const isRegister = mode === "register";
  const isVerify = mode === "verify";
  const title = isRegister ? "Create your account" : isVerify ? "Verify your email" : "Welcome back";
  const subtitle = isRegister
    ? "Create an account to manage leads and calls."
    : isVerify
      ? "Enter the six-digit code sent to your email address."
      : "Sign in to review leads and manage calls.";

  return (
    <main className="auth-shell">
      <section className="form-panel">
        <div className="auth-card">
          <p className="eyebrow">T Rex</p>
          <h1>{title}</h1>
          <p className="subtitle">{subtitle}</p>
          <form onSubmit={submit}>
            <label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
            {isVerify ? (
              <label>Verification code<input type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} required /></label>
            ) : (
              <label>Password<input type="password" minLength={isRegister ? 10 : undefined} value={password} onChange={(event) => setPassword(event.target.value)} required />{isRegister && <small className="field-hint">Use at least 10 characters.</small>}</label>
            )}
            {notice && <div className="notice" role="status">{notice}</div>}
            {error && <div className="notice error" role="alert">{error}</div>}
            <button className="primary" disabled={loading}>{loading ? "Please wait..." : isRegister ? "Create account" : isVerify ? "Verify email" : "Sign in"}</button>
            {isVerify && <button className="ghost" type="button" disabled={loading || !email} onClick={resendVerification}>Resend verification code</button>}
          </form>
          <p className="auth-links">{isRegister ? <>Already have an account? <Link to="/auth/login">Sign in</Link></> : isVerify ? <>Return to <Link to="/auth/login">sign in</Link></> : <>Need an account? <Link to="/auth/register">Create one</Link></>}</p>
        </div>
      </section>
    </main>
  );
}
