import { type FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AlertCircle, ArrowLeft, CheckCircle2, Loader2, Phone } from "lucide-react";
import { authApi } from "../api/auth";
import { saveSession } from "./auth";

/* ═══════════════════════════════════════════════════════════════════════
   Shared UI pieces
═══════════════════════════════════════════════════════════════════════ */

function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="auth-outer">
      <div className="auth-card">
        {/* Logo */}
        <div className="auth-logo">
          <div className="auth-logo-mark">T</div>
          <div>
            <div className="auth-logo-name">T Rex</div>
            <div className="auth-logo-sub">Calling Engine</div>
          </div>
        </div>
        {children}
      </div>
      <p className="auth-footer">
        T Rex Platform · Enterprise AI Sales System
      </p>
    </div>
  );
}

function Field({
  label, type = "text", value, onChange, hint, autoComplete,
}: {
  label: string; type?: string; value: string;
  onChange: (v: string) => void; hint?: string; autoComplete?: string;
}) {
  return (
    <div className="auth-field">
      <label className="auth-label">{label}</label>
      <input
        className="auth-input"
        type={type}
        value={value}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        required
      />
      {hint && <span className="auth-hint">{hint}</span>}
    </div>
  );
}

function Notice({ kind, text }: { kind: "error" | "success"; text: string }) {
  return (
    <div className={`auth-notice auth-notice--${kind}`}>
      {kind === "error"
        ? <AlertCircle size={14} />
        : <CheckCircle2 size={14} />}
      <span>{text}</span>
    </div>
  );
}

function SubmitBtn({ loading, label }: { loading: boolean; label: string }) {
  return (
    <button className="auth-submit" type="submit" disabled={loading}>
      {loading ? <Loader2 size={15} className="spin" /> : null}
      {loading ? "Please wait…" : label}
    </button>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   LOGIN
═══════════════════════════════════════════════════════════════════════ */
export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail]       = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  const registeredMsg = params.get("registered") === "1"
    ? "Account created — sign in below."
    : null;
  const resetMsg = params.get("reset") === "1"
    ? "Password reset — sign in with your new password."
    : null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      const session = await authApi.login(email, password);
      saveSession(session.access_token, session.refresh_token);
      navigate("/calling", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      <div className="auth-heading">
        <h1>Welcome back</h1>
        <p>Sign in to manage calls and leads.</p>
      </div>

      {registeredMsg && <Notice kind="success" text={registeredMsg} />}
      {resetMsg      && <Notice kind="success" text={resetMsg} />}

      <form onSubmit={submit} className="auth-form">
        <Field label="Email address" type="email" value={email}
          onChange={setEmail} autoComplete="email" />
        <Field label="Password" type="password" value={password}
          onChange={setPassword} autoComplete="current-password"
          hint="" />
        <div className="auth-forgot-row">
          <Link to="/auth/forgot-password" className="auth-link-sm">
            Forgot password?
          </Link>
        </div>
        {error && <Notice kind="error" text={error} />}
        <SubmitBtn loading={loading} label="Sign in" />
      </form>

      <p className="auth-alt">
        No account yet?{" "}
        <Link to="/auth/register" className="auth-link">Create one</Link>
      </p>
    </AuthShell>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   REGISTER
═══════════════════════════════════════════════════════════════════════ */
export function RegisterPage() {
  const navigate = useNavigate();
  const [email, setEmail]     = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password.length < 10) {
      setError("Password must be at least 10 characters.");
      return;
    }
    setLoading(true); setError("");
    try {
      await authApi.register(email, password);
      navigate(
        `/auth/verify-email?email=${encodeURIComponent(email)}`,
        { replace: true },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      <div className="auth-heading">
        <h1>Create account</h1>
        <p>Set up your T Rex Calling Engine account.</p>
      </div>

      <form onSubmit={submit} className="auth-form">
        <Field label="Email address" type="email" value={email}
          onChange={setEmail} autoComplete="email" />
        <Field label="Password" type="password" value={password}
          onChange={setPassword} autoComplete="new-password"
          hint="At least 10 characters." />
        {error && <Notice kind="error" text={error} />}
        <SubmitBtn loading={loading} label="Create account" />
      </form>

      <p className="auth-alt">
        Already have an account?{" "}
        <Link to="/auth/login" className="auth-link">Sign in</Link>
      </p>
    </AuthShell>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   VERIFY EMAIL
═══════════════════════════════════════════════════════════════════════ */
export function VerifyEmailPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail]   = useState(params.get("email") ?? "");
  const [code, setCode]     = useState("");
  const [error, setError]   = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      await authApi.verify(email, code);
      navigate(
        `/auth/login?email=${encodeURIComponent(email)}&registered=1`,
        { replace: true },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed.");
    } finally {
      setLoading(false);
    }
  }

  async function resend() {
    setResending(true); setError(""); setSuccess("");
    try {
      await authApi.resend(email);
      setSuccess("A new code has been sent to your email.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not resend code.");
    } finally {
      setResending(false);
    }
  }

  return (
    <AuthShell>
      <div className="auth-heading">
        <h1>Verify your email</h1>
        <p>Enter the 6-digit code sent to <strong>{email || "your email"}</strong>.</p>
      </div>

      <form onSubmit={submit} className="auth-form">
        {!email && (
          <Field label="Email address" type="email" value={email}
            onChange={setEmail} autoComplete="email" />
        )}
        <Field label="Verification code" type="text" value={code}
          onChange={setCode} autoComplete="one-time-code" />
        {error   && <Notice kind="error"   text={error} />}
        {success && <Notice kind="success" text={success} />}
        <SubmitBtn loading={loading} label="Verify email" />
      </form>

      <p className="auth-alt">
        Didn't get a code?{" "}
        <button
          type="button"
          className="auth-link"
          onClick={resend}
          disabled={resending}
          style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
        >
          {resending ? "Sending…" : "Resend"}
        </button>
      </p>

      <p className="auth-alt" style={{ marginTop: 4 }}>
        <Link to="/auth/login" className="auth-link-sm">
          <ArrowLeft size={12} style={{ display: "inline", verticalAlign: "middle" }} />{" "}
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   FORGOT PASSWORD
═══════════════════════════════════════════════════════════════════════ */
export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [email, setEmail]   = useState("");
  const [error, setError]   = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true); setError(""); setSuccess("");
    try {
      await authApi.forgot(email);
      setSuccess("If the account exists, a reset code has been sent.");
      setTimeout(() => {
        navigate(`/auth/reset-password?email=${encodeURIComponent(email)}`);
      }, 1800);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      <div className="auth-heading">
        <h1>Reset password</h1>
        <p>We'll send a 6-digit code to your email address.</p>
      </div>

      <form onSubmit={submit} className="auth-form">
        <Field label="Email address" type="email" value={email}
          onChange={setEmail} autoComplete="email" />
        {error   && <Notice kind="error"   text={error} />}
        {success && <Notice kind="success" text={success} />}
        <SubmitBtn loading={loading} label="Send reset code" />
      </form>

      <p className="auth-alt">
        <Link to="/auth/login" className="auth-link-sm">
          <ArrowLeft size={12} style={{ display: "inline", verticalAlign: "middle" }} />{" "}
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   RESET PASSWORD
═══════════════════════════════════════════════════════════════════════ */
export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail]       = useState(params.get("email") ?? "");
  const [code, setCode]         = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm]   = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password.length < 10) { setError("Password must be at least 10 characters."); return; }
    if (password !== confirm)  { setError("Passwords do not match."); return; }
    setLoading(true); setError("");
    try {
      await authApi.reset(email, code, password);
      navigate(
        `/auth/login?email=${encodeURIComponent(email)}&reset=1`,
        { replace: true },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      <div className="auth-heading">
        <h1>Set new password</h1>
        <p>Enter the code from your email and choose a new password.</p>
      </div>

      <form onSubmit={submit} className="auth-form">
        {!email && (
          <Field label="Email address" type="email" value={email}
            onChange={setEmail} autoComplete="email" />
        )}
        <Field label="Reset code" type="text" value={code}
          onChange={setCode} autoComplete="one-time-code" />
        <Field label="New password" type="password" value={password}
          onChange={setPassword} autoComplete="new-password"
          hint="At least 10 characters." />
        <Field label="Confirm password" type="password" value={confirm}
          onChange={setConfirm} autoComplete="new-password" />
        {error && <Notice kind="error" text={error} />}
        <SubmitBtn loading={loading} label="Reset password" />
      </form>

      <p className="auth-alt">
        <Link to="/auth/forgot-password" className="auth-link-sm">
          <ArrowLeft size={12} style={{ display: "inline", verticalAlign: "middle" }} />{" "}
          Back
        </Link>
      </p>
    </AuthShell>
  );
}

/* ═══════════════════════════════════════════════════════════════════════
   Phone icon — just a visual flourish used in AuthShell
═══════════════════════════════════════════════════════════════════════ */
export { Phone };
