import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/layouts/AppShell";
import { LeadSummaryPage } from "@/pages/LeadSummaryPage";
import { ReportDetailPage } from "@/pages/ReportDetailPage";
import { ReportsOverviewPage } from "@/pages/ReportsOverviewPage";

export function AppRouter() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/reports" replace />} />
        <Route path="/reports" element={<ReportsOverviewPage />} />
        <Route path="/reports/:reportId" element={<ReportDetailPage />} />
        <Route path="/reports/leads/:leadId" element={<LeadSummaryPage />} />
        <Route path="*" element={<Navigate to="/reports" replace />} />
      </Routes>
    </AppShell>
  );
}