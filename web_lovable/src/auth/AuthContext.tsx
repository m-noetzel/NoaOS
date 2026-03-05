import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { apiRequest } from "@/api/client";
import type { AuthTokens, LoginRequest } from "@/api/types";
import { setTokens, clearTokens, hasTokens } from "./tokens";

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => hasTokens());
  const [isLoading, setIsLoading] = useState(false);

  // Check token presence on mount
  useEffect(() => {
    setIsAuthenticated(hasTokens());
  }, []);

  const login = useCallback(async (identifier: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await apiRequest<AuthTokens>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ identifier, password } satisfies LoginRequest),
      });

      if (res.error) {
        throw new Error(res.error.message);
      }

      setTokens(res.data.access_token, res.data.refresh_token);
      setIsAuthenticated(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setIsAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
