import "@testing-library/jest-dom";
import { afterEach, vi } from "vitest";

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
});

// Ensure doMock registrations from one test don't leak to subsequent tests.
// vitest's vi.resetModules() only clears the module cache, not mock registrations.
// vi.doUnmock() is needed to clear specific doMock registrations between tests.
afterEach(() => {
  vi.doUnmock("@/api/sse");
  vi.doUnmock("@/api/client");
  vi.doUnmock("@/auth/AuthContext");
});
