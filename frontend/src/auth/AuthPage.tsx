import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";

export function AuthPage({ mode = "login" }: { mode?: "login" | "register" }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "register") {
        await authApi.register(email, password);
        navigate(`/auth/login?registered=1&email=${encodeURIComponent(email)}`, { replace: true });
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

  return (
    <main className="auth-shell">
      <section className="form-panel">
        <div className="auth-card">
          <p className="eyebrow">T Rex</p>
          <h1>{mode === "register" ? "Create your account" : "Welcome back"}</h1>
          <p className="subtitle">{mode === "register" ? "Create an account to manage leads and calls." : "Sign in to review leads and manage calls."}</p>
          <form onSubmit={submit}>
            <label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
            <label>Password<input type="password" minLength={10} value={password} onChange={(event) => setPassword(event.target.value)} required /><small className="field-hint">Use at least 10 characters.</small></label>
            {error && <div className="notice error" role="alert">{error}</div>}
            <button className="primary" disabled={loading}>{loading ? "Please wait..." : mode === "register" ? "Create account" : "Sign in"}</button>
          </form>
          <p className="auth-links">{mode === "register" ? <>Already have an account? <Link to="/auth/login">Sign in</Link></> : <>Need an account? <Link to="/auth/register">Create one</Link></>}</p>
        </div>
      </section>
    </main>
  );
}
