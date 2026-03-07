import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiRequest, WEB_DEVICE_ID } from "@/api/client";
import type { LoginRequest, RegisterRequest } from "@/api/types";
import { setTokens, clearTokens, hasTokens } from "./tokens";

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
  const [isAuthenticated, setIsAuthenticated] = useState(() => hasTokens());
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setIsAuthenticated(hasTokens());
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const body: LoginRequest = { email, password, device_id: WEB_DEVICE_ID };
      const res = await apiRequest<{ authenticated: boolean }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      });

      if (!res.ok || res.error) {
        throw new Error(res.error?.message || "Login failed");
      }

      // C6: Tokens are in httpOnly cookies; just track auth state
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
