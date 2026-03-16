/**
 * Frontend tests for Phase CQ8 — SSE contract helpers.
 *
 * Tests for the asString / asRecord / asStringArray helper functions
 * that replace unsafe `as string` casts in SSE event consumers.
 *
 * These helpers ensure that unknown data from backend SSE events is
 * safely narrowed to the expected type without TypeScript unsafe casts.
 */

import { describe, it, expect } from "vitest";
import { asString, asRecord, asStringArray } from "@/lib/utils";

describe("asString — safe unknown → string narrowing", () => {
  it("returns the string unchanged when value is a string", () => {
    expect(asString("hello")).toBe("hello");
  });

  it("returns fallback empty string when value is undefined", () => {
    expect(asString(undefined)).toBe("");
  });

  it("returns fallback empty string when value is null", () => {
    expect(asString(null)).toBe("");
  });

  it("returns fallback empty string when value is a number", () => {
    expect(asString(42)).toBe("");
  });

  it("returns fallback empty string when value is an object", () => {
    expect(asString({ key: "value" })).toBe("");
  });

  it("returns custom fallback when value is not a string", () => {
    expect(asString(undefined, "default")).toBe("default");
  });

  it("handles empty string correctly (not replaced with fallback)", () => {
    expect(asString("", "default")).toBe("");
  });

  it("handles SSE run_id field safely", () => {
    // Simulate event.data.run_id from a MetaEvent
    const data: Record<string, unknown> = { run_id: "run-abc-123" };
    expect(asString(data.run_id)).toBe("run-abc-123");
  });

  it("handles missing SSE field gracefully", () => {
    const data: Record<string, unknown> = {};
    expect(asString(data.run_id)).toBe("");
  });
});

describe("asRecord — safe unknown → Record<string, unknown> narrowing", () => {
  it("returns the record unchanged when value is a plain object", () => {
    const obj = { tool: "gmail", args: {} };
    expect(asRecord(obj)).toEqual(obj);
  });

  it("returns empty record when value is undefined", () => {
    expect(asRecord(undefined)).toEqual({});
  });

  it("returns empty record when value is null", () => {
    expect(asRecord(null)).toEqual({});
  });

  it("returns empty record when value is a string", () => {
    expect(asRecord("not-an-object")).toEqual({});
  });

  it("returns empty record when value is an array", () => {
    expect(asRecord(["item1", "item2"])).toEqual({});
  });

  it("handles nested SSE tool_call payload safely", () => {
    const data: Record<string, unknown> = {
      tool_call: { name: "web_search", input: { query: "test" } },
    };
    const tc = asRecord(data.tool_call);
    expect(asString(tc.name)).toBe("web_search");
    expect(asRecord(tc.input)).toEqual({ query: "test" });
  });
});

describe("asStringArray — safe unknown → string[] narrowing", () => {
  it("returns the array when all items are strings", () => {
    expect(asStringArray(["a", "b", "c"])).toEqual(["a", "b", "c"]);
  });

  it("filters out non-string items from a mixed array", () => {
    expect(asStringArray(["a", 1, null, "b"])).toEqual(["a", "b"]);
  });

  it("returns empty array when value is undefined", () => {
    expect(asStringArray(undefined)).toEqual([]);
  });

  it("returns empty array when value is not an array", () => {
    expect(asStringArray({ length: 3 })).toEqual([]);
  });
});
