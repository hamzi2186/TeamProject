import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "../layouts/AppShell";
import { KnowledgeDetailPage } from "../pages/KnowledgeDetailPage";
import { KnowledgePage } from "../pages/KnowledgePage";

const platformUrl = import.meta.env.VITE_PLATFORM_FRONTEND_URL ?? "http://localhost:5173";

function ProtectedShell() {
  if (sessionStorage.getItem("trex_access_token")) return <AppShell />;
  return <main className="auth-handoff"><div className="brand"><span className="brand-mark">T</span><strong>T Rex</strong></div><h1>Sign in to manage client knowledge</h1><p>Knowledge uses your existing T Rex platform session. No separate account is required.</p><a className="primary-button" href={`${platformUrl}/auth/login`}>Open T Rex sign in</a></main>;
}

export function App() {
  return <Routes><Route element={<ProtectedShell />}><Route path="/knowledge" element={<KnowledgePage />} /><Route path="/knowledge/:websiteId" element={<KnowledgeDetailPage />} /><Route path="/" element={<Navigate to="/knowledge" replace />} /></Route><Route path="*" element={<Navigate to="/knowledge" replace />} /></Routes>;
}

