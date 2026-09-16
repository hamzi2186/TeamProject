import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AppShell } from "../layouts/AppShell";
import { ReportsOverviewPage } from "../pages/ReportsOverviewPage";
import { ReportDetailPage } from "../pages/ReportDetailPage";
import { LeadSummaryPage } from "../pages/LeadSummaryPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 1000 * 30, // 30 seconds
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell>
          <Routes>
            <Route path="/" element={<Navigate to="/reports" replace />} />
            <Route path="/reports" element={<ReportsOverviewPage />} />
            <Route path="/reports/:reportId" element={<ReportDetailPage />} />
            <Route path="/reports/leads/:leadId" element={<LeadSummaryPage />} />
            <Route path="*" element={<Navigate to="/reports" replace />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  );
};
