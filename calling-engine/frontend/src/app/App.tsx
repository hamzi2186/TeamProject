import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, Routes, NavLink, useLocation } from "react-router-dom";
import {
  PhoneCall, BarChart3, Settings, HelpCircle, Zap, LayoutGrid, LogOut,
} from "lucide-react";
import { CallingListPage }  from "../pages/Calling/index";
import { CallDetailPage }   from "../pages/Calling/CallDetailPage";
import { AuthGuard }        from "../auth/AuthGuard";
import {
  LoginPage,
  RegisterPage,
  VerifyEmailPage,
  ForgotPasswordPage,
  ResetPasswordPage,
} from "../auth/AuthPage";
import { authApi }          from "../api/auth";
import { clearSession, getUserFromToken } from "../auth/auth";
import { useNavigate }      from "react-router-dom";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: true } },
});

/* ── Sidebar ──────────────────────────────────────────────────────────── */
function Sidebar() {
  const navigate  = useNavigate();
  const user      = getUserFromToken();
  const initials  = user?.email?.charAt(0).toUpperCase() ?? "U";

  async function logout() {
    try { await authApi.logout(); } catch { /* ignore */ }
    clearSession();
    navigate("/auth/login", { replace: true });
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-logo">T</div>
        <div>
          <div className="brand-name">T Rex</div>
          <div className="brand-sub">Calling Engine</div>
        </div>
      </div>

      <div className="sidebar-section">
        <div className="sidebar-label">Workspace</div>

        <NavLink
          to="/calling"
          className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
        >
          <PhoneCall size={15} />
          Voice Calls
          <span className="nav-dot" />
        </NavLink>

        <a className="sidebar-link" style={{ opacity: 0.4, cursor: "not-allowed" }}>
          <BarChart3 size={15} />
          Analytics
        </a>

        <a className="sidebar-link" style={{ opacity: 0.4, cursor: "not-allowed" }}>
          <LayoutGrid size={15} />
          Campaigns
        </a>

        <div className="sidebar-label" style={{ marginTop: 16 }}>System</div>

        <a className="sidebar-link" style={{ opacity: 0.4, cursor: "not-allowed" }}>
          <Zap size={15} />
          Integrations
        </a>

        <a className="sidebar-link" style={{ opacity: 0.4, cursor: "not-allowed" }}>
          <Settings size={15} />
          Settings
        </a>

        <a className="sidebar-link" style={{ opacity: 0.4, cursor: "not-allowed" }}>
          <HelpCircle size={15} />
          Help & Docs
        </a>
      </div>

      <div className="sidebar-footer">
        {/* User row */}
        {user && (
          <div
            style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "8px 10px", marginBottom: 6,
            }}
          >
            <div
              style={{
                width: 26, height: 26, borderRadius: "50%",
                background: "var(--accent)", color: "var(--sb-bg)",
                display: "grid", placeItems: "center",
                fontSize: 11, fontWeight: 700, flexShrink: 0,
              }}
            >
              {initials}
            </div>
            <span
              style={{
                fontSize: 12, color: "var(--sb-text-hi)",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1,
              }}
            >
              {user.email || "User"}
            </span>
            <button
              onClick={logout}
              title="Sign out"
              style={{
                background: "none", border: "none", cursor: "pointer",
                color: "var(--sb-text)", padding: 4, borderRadius: 4,
                display: "grid", placeItems: "center",
                flexShrink: 0,
              }}
            >
              <LogOut size={13} />
            </button>
          </div>
        )}

        {/* Live status */}
        <div className="sidebar-status">
          <div className="status-dot" />
          <div className="sidebar-status-text">
            <strong>Engine Live</strong>
            <span>Vapi · Auto-refresh 15s</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

/* ── Topbar ───────────────────────────────────────────────────────────── */
function Topbar() {
  const location = useLocation();
  const isDetail = /\/calling\/.+/.test(location.pathname);

  return (
    <div className="topbar">
      <div className="topbar-breadcrumb">
        <span style={{ color: "var(--tx-lo)" }}>T Rex</span>
        <span className="sep">/</span>
        <span>Calling Engine</span>
        {isDetail && (
          <>
            <span className="sep">/</span>
            <span>Call Detail</span>
          </>
        )}
      </div>
      <div className="topbar-spacer" />
      <div className="topbar-badge">
        <span className="live-dot" />
        Live · 15s refresh
      </div>
    </div>
  );
}

/* ── Protected shell ──────────────────────────────────────────────────── */
function AppShell() {
  return (
    <AuthGuard>
      <div className="app-shell">
        <Sidebar />
        <div className="workspace">
          <Topbar />
          <div className="page-content">
            <Routes>
              <Route path="/"                element={<Navigate to="/calling" replace />} />
              <Route path="/calling"         element={<CallingListPage />} />
              <Route path="/calling/:callId" element={<CallDetailPage />} />
              <Route path="*"               element={<Navigate to="/calling" replace />} />
            </Routes>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
}

/* ── Root ─────────────────────────────────────────────────────────────── */
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
        {/* Public auth routes */}
        <Route path="/auth/login"          element={<LoginPage />} />
        <Route path="/auth/register"       element={<RegisterPage />} />
        <Route path="/auth/verify-email"   element={<VerifyEmailPage />} />
        <Route path="/auth/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/auth/reset-password"  element={<ResetPasswordPage />} />

        {/* All other routes → protected shell */}
        <Route path="/*" element={<AppShell />} />
      </Routes>
    </QueryClientProvider>
  );
}
