import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Route, Routes, Navigate } from "react-router-dom";
import { AuthGuard } from "../auth/AuthGuard";
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

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthGuard>
        <Routes>
          <Route path="/calling" element={<CallingListPage />} />
          <Route path="/calling/:callId" element={<CallDetailPage />} />
          {/* Default redirect to calling list */}
          <Route path="/" element={<Navigate to="/calling" replace />} />
          <Route path="*" element={<Navigate to="/calling" replace />} />
        </Routes>
      </AuthGuard>
    </QueryClientProvider>
  );
}