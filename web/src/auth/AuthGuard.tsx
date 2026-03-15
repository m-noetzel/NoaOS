import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  // AU1: Hold render until the /auth/me startup check resolves.
  // Prevents flash of protected content before session is verified,
  // and prevents premature redirect to /login when cookies are valid.
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
