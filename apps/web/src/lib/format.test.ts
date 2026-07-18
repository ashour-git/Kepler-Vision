import { describe, expect, it } from "vitest";

import { formatNumber, formatRelativeTime } from "./format";

describe("formatNumber", () => {
  it("formats integers with grouping", () => {
    expect(formatNumber(1234)).toBe("1,234");
  });

  it("respects Intl options", () => {
    expect(formatNumber(0.42, { style: "percent" })).toBe("42%");
  });
});

describe("formatRelativeTime", () => {
  it("returns a relative string for a recent date", () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60_000);
    const out = formatRelativeTime(fiveMinAgo);
    expect(out).toMatch(/5 minutes ago|now/);
  });

  it("handles invalid input", () => {
    expect(formatRelativeTime("not a date")).toBe("—");
  });
});
