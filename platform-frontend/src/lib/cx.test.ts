/**
 * cx is hand-rolled in place of clsx and is used by every component to apply
 * conditional variants. A regression here is invisible in review but strips
 * styling app-wide, so the falsy-filtering contract is pinned explicitly.
 */

import { describe, expect, it } from "vitest";

import { cx } from "@/lib/cx";

describe("cx", () => {
  it("joins class names with a single space", () => {
    expect(cx("btn", "btnGhost")).toBe("btn btnGhost");
  });

  it("drops false, null and undefined so conditional variants collapse cleanly", () => {
    expect(cx("btn", false, null, undefined, "active")).toBe("btn active");
  });

  it("drops empty strings rather than emitting a double space", () => {
    // CSS-module lookups widen to `string | undefined` under
    // noUncheckedIndexedAccess, so empty/undefined entries are routine here.
    expect(cx("btn", "", "active")).toBe("btn active");
  });

  it("returns an empty string when given nothing", () => {
    expect(cx()).toBe("");
  });

  it("returns an empty string when every entry is falsy", () => {
    expect(cx(false, null, undefined)).toBe("");
  });

  it("keeps a single class unchanged", () => {
    expect(cx("btn")).toBe("btn");
  });
});
