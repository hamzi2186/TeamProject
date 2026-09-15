import { FormEvent, useState } from "react";
import { ArrowRight, CheckCircle2, Mail } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";

type Mode = "login" | "register" | "verify" | "forgot" | "reset";

const labels: Record<Mode, { title: string; subtitle: string; action: string }> = {
  login: { title: "Welcome back", subtitle: "Sign in to your T Rex workspace.", action: "Sign in" },
  register: { title: "Create your account", subtitle: "Start your autonomous outreach workspace.", action: "Create account" },
  verify: { title: "Verify your email", subtitle: "Enter the six-digit code sent to your inbox.", action: "Verify email" },
  forgot: { title: "Reset your password", subtitle: "We will send a reset code to your email.", action: "Send reset code" },
  reset: { title: "Choose a new password", subtitle: "Enter the code from your email and a new password.", action: "Reset password" },
};

export function AuthPage({ mode }: { mode: Mode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");
    try {
      if (mode === "register") {
        await authApi.register(email, password);
        navigate(`/auth/verify-email?email=${encodeURIComponent(email)}`);
      } else if (mode === "verify") {
        await authApi.verify(email, code);
        setMessage("Email verified. You can now sign in.");
      } else if (mode === "login") {
        const session = await authApi.login(email, password);
        sessionStorage.setItem("trex_access_token", session.access_token);
        navigate("/");
      } else if (mode === "forgot") {
        await authApi.forgot(email);
        navigate(`/auth/reset-password?email=${encodeURIComponent(email)}`);
      } else {
        await authApi.reset(email, code, password);
        setMessage("Password reset. You can now sign in.");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  async function resend() {
    setError("");
    try {
      const result = await authApi.resend(email);
      setMessage(result.message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not resend code.");
    }
  }

  const content = labels[mode];
  const needsPassword = mode === "login" || mode === "register" || mode === "reset";
  const needsCode = mode === "verify" || mode === "reset";

  return (
    <main className="auth-shell">
      <section className="brand-panel">
        <div className="brand-mark">T</div>
        <div className="brand-copy">
          <p className="eyebrow">T Rex</p>
          <h1>Hunt Leads.<br />Command Conversions.</h1>
          <p>Autonomous outreach powered by real client intelligence.</p>
        </div>
        <div className="trust-line"><CheckCircle2 size={16} /> Secure first-party authentication</div>
      </section>
      <section className="form-panel">
        <div className="auth-card">
          <div className="mobile-brand">T Rex</div>
          <div className="icon-box"><Mail size={20} /></div>
          <h2>{content.title}</h2>
          <p className="subtitle">{content.subtitle}</p>
          <form onSubmit={submit}>
            <label>Email address<input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
            {needsCode && <label>Six-digit code<input className="otp" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]{6}" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} required /></label>}
            {needsPassword && <label>{mode === "reset" ? "New password" : "Password"}<input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={10} value={password} onChange={(e) => setPassword(e.target.value)} required /></label>}
            {error && <div className="notice error" role="alert">{error}</div>}
            {message && <div className="notice success" role="status">{message}</div>}
            <button className="primary" disabled={loading}>{loading ? "Please wait…" : content.action}<ArrowRight size={16} /></button>
          </form>
          <div className="auth-links">
            {mode === "login" && <><Link to="/auth/forgot-password">Forgot password?</Link><span>New to T Rex? <Link to="/auth/register">Create account</Link></span></>}
            {mode === "register" && <span>Already have an account? <Link to="/auth/login">Sign in</Link></span>}
            {mode === "verify" && <><button className="text-button" onClick={resend}>Resend code</button><Link to="/auth/login">Back to sign in</Link></>}
            {(mode === "forgot" || mode === "reset") && <Link to="/auth/login">Back to sign in</Link>}
          </div>
        </div>
      </section>
    </main>
  );
}
