import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Safely extract a string value from an unknown field.
 *
 * Avoids `as string` casts on `Record<string, unknown>` data from the
 * backend (SSE events, run events, etc.).  Returns `fallback` when the
 * value is absent, null, or not a string.
 */
export function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

/**
 * Safely extract a string[] value from an unknown field.
 */
export function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((v): v is string => typeof v === "string");
}

/**
 * Safely extract a Record<string, unknown> value from an unknown field.
 */
export function asRecord(value: unknown): Record<string, unknown> {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}
