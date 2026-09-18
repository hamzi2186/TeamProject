import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { StatusBadge } from "@/components/shared/StatusBadge";

describe("StatusBadge", () => {
  it("maps INTERESTED to the interested label with a success tone", () => {
    render(<StatusBadge status="INTERESTED" />);
    const badge = screen.getByText("Interested");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("aria-label", "Status: Interested");
  });

  it("maps DO_NOT_CONTACT to the do not contact label", () => {
    render(<StatusBadge status="DO_NOT_CONTACT" />);
    expect(screen.getByText("Do not contact")).toBeInTheDocument();
  });

  it("falls back to title-casing unknown statuses", () => {
    render(<StatusBadge status="SCHEDULED" />);
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });

  it("labels report processing status", () => {
    render(<StatusBadge status="PROCESSING" />);
    expect(screen.getByText("Processing")).toBeInTheDocument();
  });
});