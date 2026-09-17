import { Navigate, Route, Routes } from "react-router-dom";
import { isAuthenticated } from "../auth/auth";
import { AgentPage } from "../pages/AgentPage";

const platformUrl = import.meta.env.VITE_PLATFORM_FRONTEND_URL ?? "http://localhost:5173";

function ProtectedAgent() {
  if (!isAuthenticated()) {
    return (
      <main className="agent-auth-handoff">
        <div className="agent-auth-card">
          <div className="agent-auth-brand">
            <span className="agent-auth-mark">T</span>
            <strong>T Rex Agent Engine</strong>
          </div>
          <h1>Open Agent through the T Rex platform</h1>
          <p>
            The Agent Engine uses your active T Rex platform session.
            Access Agent via the platform navigation or sign in to continue.
          </p>
          <a className="agent-auth-button" href={`${platformUrl}/agent`}>
            Open in T Rex Platform
          </a>
        </div>
      </main>
    );
  }

  return <AgentPage />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<ProtectedAgent />} />
      <Route path="/:conversationId" element={<ProtectedAgent />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
