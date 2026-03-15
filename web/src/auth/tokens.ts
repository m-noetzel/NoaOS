// AU1: Auth state is determined by the /auth/me startup check, not localStorage.
// Tokens are in httpOnly cookies — not accessible to JS. This module is kept
// as a stub so callers don't need to be updated for the no-op functions.

export function getAccessToken(): string | null {
  // Tokens are in httpOnly cookies — not readable by JS.
  return null;
}

export function getRefreshToken(): string | null {
  return null;
}

export function setTokens(_access: string, _refresh: string): void {
  // AU1: No-op. Auth state lives in React state (AuthContext), not localStorage.
  // Tokens are set as httpOnly cookies by the server.
}

export function clearTokens(): void {
  // AU1: No-op. Auth state is managed by React state reset.
}

export function hasTokens(): boolean {
  // AU1: Always returns false — startup check via /auth/me is the source of truth.
  return false;
}
