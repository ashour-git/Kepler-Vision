import { describe, expect, it } from "vitest";

import { cn } from "./cn";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("ignores falsy values", () => {
    expect(cn("a", undefined, null, false, "b")).toBe("a b");
  });

  it("resolves tailwind conflicts (later wins)", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
  });
});
