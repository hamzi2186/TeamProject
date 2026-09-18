import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  fetchDailyReports,
  fetchLeadJourney,
  fetchReportDetail,
  generateDailyReport,
} from "@/api/reports";

export function useDailyReports(page = 1, pageSize = 30) {
  return useQuery({
    queryKey: ["dailyReports", page, pageSize],
    queryFn: () => fetchDailyReports(page, pageSize),
  });
}

export function useReportDetail(reportId: string | undefined) {
  return useQuery({
    queryKey: ["reportDetail", reportId],
    queryFn: () => fetchReportDetail(reportId as string),
    enabled: Boolean(reportId),
  });
}

export function useLeadJourney(leadId: string | undefined) {
  return useQuery({
    queryKey: ["leadJourney", leadId],
    queryFn: () => fetchLeadJourney(leadId as string),
    enabled: Boolean(leadId),
  });
}

export function useGenerateDailyReport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (reportDate?: string) => generateDailyReport(reportDate),
    onSuccess: (report) => {
      queryClient.invalidateQueries({ queryKey: ["dailyReports"] });
      toast.success("Report generated", {
        description: `Completed for ${report.report_date} with ${report.total_leads} leads reviewed.`,
      });
    },
    onError: (error: Error) => {
      toast.error("Could not generate the report", {
        description: error.message || "The request could not be completed.",
      });
    },
  });
}