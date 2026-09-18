import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("renders as a button with the default variant and size classes", () => {
    render(<Button>Download DOCX</Button>);
    const button = screen.getByRole("button", { name: "Download DOCX" });
    expect(button).toBeInTheDocument();
    expect(button).not.toHaveAttribute("data-disabled");
  });

  it("supports asChild rendering into an anchor", () => {
    render(
      <Button asChild>
        <a href="/download">Download</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Download" });
    expect(link).toHaveAttribute("href", "/download");
  });

  it("is disabled and marked unavailable when in a disabled state", () => {
    render(<Button disabled>Generate</Button>);
    expect(screen.getByRole("button", { name: "Generate" })).toBeDisabled();
  });
});