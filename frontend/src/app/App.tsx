import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthGuard } from "../auth/AuthGuard";
import { AuthPage } from "../auth/AuthPage";
import { AppShell } from "./AppShell";
import { HubSpotPage } from "../hubspot/HubSpotPage";
import { LeadDetailPage } from "../leads/LeadDetailPage";
import { LeadsPage } from "../leads/LeadsPage";
import { CallDetailPage } from "../pages/Calling/CallDetailPage";
import { CallingListPage } from "../pages/Calling/index";
import { EngineHub } from "../pages/EngineHub";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
});

function ProtectedLayout() {
  return (
    <AuthGuard>
      <AppShell />
    </AuthGuard>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route element={<ProtectedLayout />}>
          <Route path="/" element={<EngineHub />} />
          <Route path="/calling" element={<CallingListPage />} />
          <Route path="/calling/:callId" element={<CallDetailPage />} />
          <Route path="/hubspot" element={<HubSpotPage />} />
          <Route path="/leads" element={<LeadsPage />} />
          <Route path="/leads/:leadId" element={<LeadDetailPage />} />
        </Route>
        <Route path="/auth/login" element={<AuthPage mode="login" />} />
        <Route path="/auth/register" element={<AuthPage mode="register" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </QueryClientProvider>
  );
}
