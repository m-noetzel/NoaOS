/**
 * GoogleCallback — handles the redirect from Google OAuth2 consent.
 *
 * The backend (GO1) handles token exchange and redirects the user here
 * at /settings?google=connected or /settings?error=... After 2 seconds
 * we redirect to /settings.
 *
 * NOTE: This page handles the case where the user is sent to /auth/google/callback
 * directly from Google (if the redirect_uri was set to the frontend).
 * In GO1's design the backend handles the callback, so this page is only reached
 * if the backend redirects here after a failure, or for future frontend-handled flows.
 *
 * Primary use: the backend sends the user to /settings?google=connected after
 * successful OAuth. This GoogleCallback page lives at /auth/google/callback and
 * handles the Google → frontend redirect scenario.
 */
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

export default function GoogleCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [countdown, setCountdown] = useState(2);

  const googleParam = searchParams.get("google");
  const errorParam = searchParams.get("error");

  const isSuccess = googleParam === "connected";
  const isError = !!errorParam;

  useEffect(() => {
    const interval = setInterval(() => {
      setCountdown((c) => c - 1);
    }, 1000);

    const timeout = setTimeout(() => {
      navigate("/settings", { replace: true });
    }, 2000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-4 rounded-lg border p-8 text-center shadow-sm">
        {isSuccess && (
          <>
            <div className="text-4xl" aria-label="success">✓</div>
            <h1 className="text-lg font-semibold">Google account connected</h1>
            <p className="text-sm text-muted-foreground">
              Your Google account has been connected successfully.
            </p>
          </>
        )}

        {isError && (
          <>
            <div className="text-4xl" aria-label="error">✗</div>
            <h1 className="text-lg font-semibold">Connection failed</h1>
            <p className="text-sm text-muted-foreground">
              {errorParam === "access_denied"
                ? "You denied access to your Google account."
                : `Google OAuth error: ${errorParam}`}
            </p>
          </>
        )}

        {!isSuccess && !isError && (
          <>
            <h1 className="text-lg font-semibold">Processing...</h1>
            <p className="text-sm text-muted-foreground">
              Completing Google connection.
            </p>
          </>
        )}

        <p className="text-xs text-muted-foreground">
          Redirecting to settings in {countdown}s…
        </p>
      </div>
    </div>
  );
}
