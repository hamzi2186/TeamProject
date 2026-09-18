import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { ReportsOverviewPage } from "@/pages/ReportsOverviewPage";
import type { IdeaReportRun } from "@/types/reports";

vi.mock("@/features/reports/hooks/use-reports", () => ({
  useDailyReports: vi.fn(),
  useGenerateDailyReport: vi.fn(),
}));

import { useDailyReports, useGenerateDailyReport } from "@/features/reports/hooks/use-reports";

function makeReport(id: string, reportDate: string, interested: number): IdeaReportRun {
  return {
    id,
    report_date: reportDate,
    status: "COMPLETED",
    total_leads: 12,
    summary_counts: {
      total_leads: 12,
      interested,
      not_interested: 1,
      follow_up_required: 2,
      converted: 1,
      no_answer: 3,
      no_response: 4,
      do_not_contact: 1,
      failed: 0,
      contacting: 0,
      new: 0,
    },
    generated_at: "2026-09-16T17:00:00Z",
    created_at: "2026-09-16T00:00:00Z",
    updated_at: "2026-09-16T17:00:00Z",
  };
}

const mockedUseDailyReports = vi.mocked(useDailyReports);
const mockedUseGenerateDailyReport = vi.mocked(useGenerateDailyReport);

describe("ReportsOverviewPage", () => {
  it("shows a loading skeleton while fetching", () => {
    mockedUseDailyReports.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDailyReports>);
    mockedUseGenerateDailyReport.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useGenerateDailyReport>);

    render(
      <MemoryRouter>
        <ReportsOverviewPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "Daily lead reports" })).toBeInTheDocument();
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders metrics and the report history table", async () => {
    mockedUseDailyReports.mockReturnValue({
      data: [makeReport("r1", "2026-09-16", 5)],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDailyReports>);
    mockedUseGenerateDailyReport.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useGenerateDailyReport>);

    render(
      <MemoryRouter>
        <ReportsOverviewPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("Report history")).toBeInTheDocument();
    expect(screen.getByText("2026-09-16")).toBeInTheDocument();
    expect(screen.getByText(/^5 Interested$/)).toBeInTheDocument();

    const download = screen.getByRole("link", { name: /Download DOCX/ });
    expect(download).toHaveAttribute("href", "http://localhost:8006/idea/reports/r1/download");
  });

  it("triggers generation from the header button", async () => {
    const user = userEvent.setup();
    mockedUseDailyReports.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as unknown as ReturnType<typeof useDailyReports>);
    const mutate = vi.fn();
    mockedUseGenerateDailyReport.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof useGenerateDailyReport>);

    render(
      <MemoryRouter>
        <ReportsOverviewPage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole("button", { name: /^Generate report$/ }));
    await waitFor(() => expect(mutate).toHaveBeenCalledOnce());
  });
});