import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { apiRequest, BASE_URL, registerSessionExpiredHandler, WEB_DEVICE_ID } from "@/api/client";
import type { LoginRequest, RegisterRequest } from "@/api/types";
import { clearTokens, setTokens } from "./tokens";

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  // AU1: Start unauthenticated + loading — /auth/me check on mount is the source of truth.
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // FE-M2: Register a React Router navigate handler so that session expiry
  // uses navigate("/login") instead of window.location.href, keeping React
  // state intact (QueryClient cache, component tree, etc.).
  useEffect(() => {
    registerSessionExpiredHandler(() => {
      clearTokens();
      queryClient.clear();
      setIsAuthenticated(false);
      navigate("/login", { replace: true });
    });
    // Cleanup: clear the handler when AuthProvider unmounts so a stale closure
    // cannot fire against a dead component tree (e.g. during hot-reload).
    return () => { registerSessionExpiredHandler(() => {}); };
  }, [navigate, queryClient]);

  // AU1: Startup session check — call /auth/me directly via fetch (not apiRequest)
  // to avoid circular 401-retry logic. If /auth/me returns 401, attempt a token
  // refresh before giving up — the access token may have expired while the refresh
  // token is still valid (e.g. after a container restart).
  useEffect(() => {
    let cancelled = false;
    const checkSession = async () => {
      try {
        let res = await fetch(`${BASE_URL}/api/v1/auth/me`, {
          method: "GET",
          credentials: "include",
        });
        // If access token expired, try refreshing before giving up
        if (!res.ok && res.status === 401) {
          const refreshRes = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: "", device_id: "web-client" }),
            credentials: "include",
          });
          if (refreshRes.ok) {
            // Retry /auth/me with the new access token cookie
            res = await fetch(`${BASE_URL}/api/v1/auth/me`, {
              method: "GET",
              credentials: "include",
            });
          }
        }
        if (!cancelled) {
          setIsAuthenticated(res.ok);
        }
      } catch {
        if (!cancelled) {
          setIsAuthenticated(false);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };
    void checkSession();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const body: LoginRequest = { email, password, device_id: WEB_DEVICE_ID };
      // AU1: skipAuthRetry=true — wrong password shows "Invalid email or password",
      // not "Session expired" from the refresh-retry cycle.
      const res = await apiRequest<{ authenticated: boolean }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
        skipAuthRetry: true,
      });

      if (!res.ok || res.error) {
        throw new Error(res.error?.message || "Login failed");
      }

      // C6: Tokens are in httpOnly cookies; just track auth state in React state
      setTokens("", "");
      setIsAuthenticated(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const body: RegisterRequest = { email, password };
      const res = await apiRequest<{ user_id: string }>("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify(body),
      });

      if (!res.ok || res.error) {
        throw new Error(res.error?.message || "Registration failed");
      }

      // Auto-login after successful registration
      await login(email, password);
    } finally {
      setIsLoading(false);
    }
  }, [login]);

  const logout = useCallback(() => {
    // Best-effort server logout
    apiRequest("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
    clearTokens();
    queryClient.clear();
    setIsAuthenticated(false);
  }, [queryClient]);

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
