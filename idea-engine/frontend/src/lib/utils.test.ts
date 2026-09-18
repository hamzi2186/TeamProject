import { describe, expect, it } from "vitest";

import { cn, formatDateTime, formatNumber } from "@/lib/utils";

describe("cn", () => {
  it("joins class names and removes falsy values", () => {
    expect(cn("a", undefined, "b", null, "c")).toBe("a b c");
  });

  it("merges conflicting tailwind classes, keeping the last", () => {
    expect(cn("p-4", "p-6")).toBe("p-6");
  });
});

describe("formatNumber", () => {
  it("formats with locale separators", () => {
    expect(formatNumber(1500)).toBe("1,500");
  });
});

describe("formatDateTime", () => {
  it("returns N/A for empty input", () => {
    expect(formatDateTime(null)).toBe("N/A");
    expect(formatDateTime(undefined)).toBe("N/A");
  });

  it("formats a valid ISO timestamp", () => {
    expect(formatDateTime("2026-09-16T17:00:00Z")).toContain("2026");
  });
});