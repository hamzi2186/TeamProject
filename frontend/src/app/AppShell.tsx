import { Bot, DatabaseZap, LayoutDashboard, LogOut, Mail, MessageSquare, PhoneCall, Users } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { clearToken } from "../auth/auth";

export function AppShell() {
  const navigate = useNavigate();

  function signOut() {
    clearToken();
    navigate("/auth/login");
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">T</span>
          <span>T Rex Platform</span>
        </div>
        <nav>
          <NavLink to="/" end>
            <LayoutDashboard size={18} />
            Dashboard
          </NavLink>
          <NavLink to="/calling">
            <PhoneCall size={18} />
            Calling Engine
          </NavLink>
          <NavLink to="/leads">
            <Users size={18} />
            Leads
          </NavLink>
          <NavLink to="/hubspot">
            <DatabaseZap size={18} />
            HubSpot
          </NavLink>
          <div className="sidebar-section-divider">Other Engines</div>
          <span className="sidebar-item disabled" title="Autonomous SMS campaign engine">
            <MessageSquare size={18} />
            SMS Engine
            <span className="badge-pill">Ready</span>
          </span>
          <span className="sidebar-item disabled" title="Cold outreach email mailer">
            <Mail size={18} />
            Mailer Engine
            <span className="badge-pill">Ready</span>
          </span>
          <a href="/agent/">
            <Bot size={18} />
            Agent Engine
          </a>
        </nav>
        <button className="sidebar-logout" onClick={signOut}>
          <LogOut size={17} />
          Sign out
        </button>
      </aside>
      <main className="workspace">
        <Outlet />
      </main>
    </div>
  );
}
