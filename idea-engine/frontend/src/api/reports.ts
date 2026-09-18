import { apiClient } from "@/api/client";
import type { IdeaReportRun, LeadJourneySummary } from "@/types/reports";

export async function fetchDailyReports(page = 1, pageSize = 30): Promise<IdeaReportRun[]> {
  return apiClient<IdeaReportRun[]>(`/idea/reports/daily?page=${page}&page_size=${pageSize}`);
}

export async function fetchReportDetail(reportId: string): Promise<IdeaReportRun> {
  return apiClient<IdeaReportRun>(`/idea/reports/${reportId}`);
}

export async function generateDailyReport(reportDate?: string): Promise<IdeaReportRun> {
  return apiClient<IdeaReportRun>("/idea/reports/daily/generate", {
    method: "POST",
    body: JSON.stringify(reportDate ? { report_date: reportDate } : {}),
  });
}

export async function fetchLeadJourney(leadId: string): Promise<LeadJourneySummary> {
  return apiClient<LeadJourneySummary>(`/idea/leads/${leadId}/summary`);
}