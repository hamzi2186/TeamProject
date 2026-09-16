import { DatabaseZap, LogOut, Users } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

export function AppShell() {
  const navigate = useNavigate();
  function signOut() {
    sessionStorage.removeItem("trex_access_token");
    navigate("/auth/login");
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand"><span className="brand-mark">T</span><span>T Rex</span></div>
        <nav>
          <NavLink to="/hubspot"><DatabaseZap size={18} />HubSpot</NavLink>
          <NavLink to="/leads"><Users size={18} />Leads</NavLink>
        </nav>
        <button className="sidebar-logout" onClick={signOut}><LogOut size={17} />Sign out</button>
      </aside>
      <main className="workspace"><Outlet /></main>
    </div>
  );
}
