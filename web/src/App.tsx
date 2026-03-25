import React, { Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "next-themes";
import { AuthProvider } from "@/auth/AuthContext";
import { AuthGuard } from "@/auth/AuthGuard";
import { AppLayout } from "@/components/layout/AppLayout";
import ErrorBoundary from "@/components/ErrorBoundary";

// BU1: Lazy-load all page-level routes for code splitting.
// Auth pages (Login, Register, ForgotPassword) are kept in a separate
// lazy group so they load quickly without pulling in the full app shell.
const Login = React.lazy(() => import("@/pages/Login"));
const Register = React.lazy(() => import("@/pages/Register"));
const ForgotPassword = React.lazy(() => import("@/pages/ForgotPassword"));
const GoogleCallback = React.lazy(() => import("@/pages/GoogleCallback"));
const NotFound = React.lazy(() => import("@/pages/NotFound"));

// Protected app pages — each becomes its own chunk
const Chat = React.lazy(() => import("@/pages/Chat"));
const Runs = React.lazy(() => import("@/pages/Runs"));
const RunDetail = React.lazy(() => import("@/pages/RunDetail"));
const Approvals = React.lazy(() => import("@/pages/Approvals"));
const Queue = React.lazy(() => import("@/pages/Queue"));
const Memory = React.lazy(() => import("@/pages/Memory"));
const Artifacts = React.lazy(() => import("@/pages/Artifacts"));
const Settings = React.lazy(() => import("@/pages/Settings"));
const Cost = React.lazy(() => import("@/pages/Cost"));
const Tools = React.lazy(() => import("@/pages/Tools"));
const Traces = React.lazy(() => import("@/pages/Traces"));
const Audit = React.lazy(() => import("@/pages/Audit"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppLayout>
        <ErrorBoundary>{children}</ErrorBoundary>
      </AppLayout>
    </AuthGuard>
  );
}

const App = () => (
  <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <AuthProvider>
            <Suspense fallback={<div className="p-6 text-muted-foreground">Loading...</div>}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/forgot-password" element={<ForgotPassword />} />
                <Route path="/" element={<ProtectedRoute><Chat /></ProtectedRoute>} />
                <Route path="/runs" element={<ProtectedRoute><Runs /></ProtectedRoute>} />
                <Route path="/runs/:runId" element={<ProtectedRoute><RunDetail /></ProtectedRoute>} />
                <Route path="/approvals" element={<ProtectedRoute><Approvals /></ProtectedRoute>} />
                <Route path="/queue" element={<ProtectedRoute><Queue /></ProtectedRoute>} />
                <Route path="/memory" element={<ProtectedRoute><Memory /></ProtectedRoute>} />
                <Route path="/artifacts" element={<ProtectedRoute><Artifacts /></ProtectedRoute>} />
                <Route path="/cost" element={<ProtectedRoute><Cost /></ProtectedRoute>} />
                <Route path="/tools" element={<ProtectedRoute><Tools /></ProtectedRoute>} />
                <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
                <Route path="/traces" element={<ProtectedRoute><Traces /></ProtectedRoute>} />
                <Route path="/audit" element={<ProtectedRoute><Audit /></ProtectedRoute>} />
                <Route path="/auth/google/callback" element={<GoogleCallback />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </AuthProvider>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  </ThemeProvider>
);

export default App;
