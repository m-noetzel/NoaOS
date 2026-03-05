import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "next-themes";
import { AuthProvider } from "@/auth/AuthContext";
import { AuthGuard } from "@/auth/AuthGuard";
import { AppLayout } from "@/components/layout/AppLayout";
import Login from "@/pages/Login";
import Chat from "@/pages/Chat";
import Runs from "@/pages/Runs";
import RunDetail from "@/pages/RunDetail";
import Approvals from "@/pages/Approvals";
import Queue from "@/pages/Queue";
import Memory from "@/pages/Memory";
import Artifacts from "@/pages/Artifacts";
import Cost from "@/pages/Cost";
import Settings from "@/pages/Settings";
import NotFound from "@/pages/NotFound";

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
      <AppLayout>{children}</AppLayout>
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
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/" element={<ProtectedRoute><Chat /></ProtectedRoute>} />
              <Route path="/runs" element={<ProtectedRoute><Runs /></ProtectedRoute>} />
              <Route path="/runs/:runId" element={<ProtectedRoute><RunDetail /></ProtectedRoute>} />
              <Route path="/approvals" element={<ProtectedRoute><Approvals /></ProtectedRoute>} />
              <Route path="/queue" element={<ProtectedRoute><Queue /></ProtectedRoute>} />
              <Route path="/memory" element={<ProtectedRoute><Memory /></ProtectedRoute>} />
              <Route path="/artifacts" element={<ProtectedRoute><Artifacts /></ProtectedRoute>} />
              <Route path="/cost" element={<ProtectedRoute><Cost /></ProtectedRoute>} />
              <Route path="/settings" element={<ProtectedRoute><Settings /></ProtectedRoute>} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  </ThemeProvider>
);

export default App;
