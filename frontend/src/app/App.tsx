import { Navigate, Route, Routes } from "react-router-dom";
import { AuthPage } from "../auth/AuthPage";
import { HubSpotPage } from "../hubspot/HubSpotPage";
import { LeadDetailPage } from "../leads/LeadDetailPage";
import { LeadsPage } from "../leads/LeadsPage";
import { AppShell } from "./AppShell";

function ProtectedShell() {
  const token = sessionStorage.getItem("trex_access_token");
  if (!token) return <Navigate to="/auth/login" replace />;
  return <AppShell />;
}

export function App() {
  return (
    <Routes>
      <Route element={<ProtectedShell />}>
        <Route path="/" element={<Navigate to="/leads" replace />} />
        <Route path="/hubspot" element={<HubSpotPage />} />
        <Route path="/leads" element={<LeadsPage />} />
        <Route path="/leads/:leadId" element={<LeadDetailPage />} />
      </Route>
      <Route path="/auth/login" element={<AuthPage mode="login" />} />
      <Route path="/auth/register" element={<AuthPage mode="register" />} />
      <Route path="/auth/verify-email" element={<AuthPage mode="verify" />} />
      <Route path="/auth/forgot-password" element={<AuthPage mode="forgot" />} />
      <Route path="/auth/reset-password" element={<AuthPage mode="reset" />} />
      <Route path="*" element={<Navigate to="/auth/login" replace />} />
    </Routes>
  );
}
