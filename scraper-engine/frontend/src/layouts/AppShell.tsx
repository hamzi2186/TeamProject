import { BookOpen, ExternalLink, LogOut } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

const platformUrl = import.meta.env.VITE_PLATFORM_FRONTEND_URL ?? "http://localhost:5173";

export function AppShell() {
  function signOut() {
    sessionStorage.removeItem("trex_access_token");
    window.location.assign(`${platformUrl}/auth/login`);
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">T</span><div><strong>T Rex</strong><small>Knowledge engine</small></div></div>
        <nav aria-label="Scraper navigation">
          <NavLink to="/knowledge"><BookOpen size={18} />Knowledge</NavLink>
        </nav>
        <div className="sidebar-footer">
          <a href={platformUrl}><ExternalLink size={16} />Platform</a>
          <button onClick={signOut}><LogOut size={16} />Sign out</button>
        </div>
      </aside>
      <section className="workspace">
        <header className="topbar"><span>Client intelligence</span><strong>Hunt Leads. Command Conversions.</strong></header>
        <Outlet />
      </section>
    </div>
  );
}

