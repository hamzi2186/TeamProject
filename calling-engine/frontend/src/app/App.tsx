import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, Routes, Link } from "react-router-dom";
import { PhoneCall } from "lucide-react";
import { CallingListPage } from "../pages/Calling/index";
import { CallDetailPage } from "../pages/Calling/CallDetailPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
});

function CallingLayout() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">T</span>
          <div>
            <strong style={{ display: "block", fontSize: 15, fontWeight: 700 }}>Calling Engine</strong>
            <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Standalone Mode</span>
          </div>
        </div>
        <nav>
          <Link to="/" className="active">
            <PhoneCall size={18} />
            Voice Outbound Calls
          </Link>
        </nav>
      </aside>
      <main className="workspace">
        <Routes>
          <Route path="/" element={<CallingListPage />} />
          <Route path="/calling" element={<CallingListPage />} />
          <Route path="/calling/:callId" element={<CallDetailPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <CallingLayout />
    </QueryClientProvider>
  );
}
