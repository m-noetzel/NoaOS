// Auth state tracking (C6: tokens are in httpOnly cookies, not accessible to JS)
const AUTH_FLAG_KEY = "noa_authenticated";

export function getAccessToken(): string | null {
  // Tokens are in httpOnly cookies — not readable by JS.
  // Return null; auth is handled by cookies sent automatically.
  return null;
}

export function getRefreshToken(): string | null {
  return null;
}

export function setTokens(_access: string, _refresh: string): void {
  // Tokens are set as httpOnly cookies by the server.
  // We only track the "authenticated" flag in localStorage.
  localStorage.setItem(AUTH_FLAG_KEY, "true");
}

export function clearTokens(): void {
  localStorage.removeItem(AUTH_FLAG_KEY);
}

export function hasTokens(): boolean {
  // Check the auth flag — actual tokens are in httpOnly cookies
  return localStorage.getItem(AUTH_FLAG_KEY) === "true";
}
