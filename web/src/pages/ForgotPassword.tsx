import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { KeyRound, ArrowLeft, CheckCircle } from "lucide-react";
import { apiRequest } from "@/api/client";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isResetting, setIsResetting] = useState(false);
  const [resetDone, setResetDone] = useState(false);
  const { toast } = useToast();

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const res = await apiRequest<{ status: string; reset_token?: string }>(
        "/api/v1/auth/forgot-password",
        { method: "POST", body: JSON.stringify({ email }) },
      );
      setSubmitted(true);
      // Self-hosted: token is returned directly in the response
      if (res.data?.reset_token) {
        setResetToken(res.data.reset_token);
      }
    } catch {
      // Always show success to prevent email enumeration
      setSubmitted(true);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast({ title: "Passwords don't match", variant: "destructive" });
      return;
    }
    if (newPassword.length < 8) {
      toast({ title: "Password must be at least 8 characters", variant: "destructive" });
      return;
    }
    setIsResetting(true);
    try {
      await apiRequest("/api/v1/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token: resetToken, new_password: newPassword }),
      });
      setResetDone(true);
      toast({ title: "Password reset successfully" });
    } catch (err) {
      toast({
        title: "Reset failed",
        description: err instanceof Error ? err.message : "Invalid or expired token",
        variant: "destructive",
      });
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center p-4 overflow-hidden bg-background">
      <div className="absolute inset-0 gradient-mesh" />
      <div className="absolute top-1/4 left-1/3 w-96 h-96 rounded-full bg-primary/5 blur-3xl animate-float" />
      <div className="absolute bottom-1/3 right-1/4 w-80 h-80 rounded-full bg-glow-secondary/5 blur-3xl animate-float" style={{ animationDelay: '1.5s' }} />

      <Card className="relative w-full max-w-sm glass-strong glow-sm animate-fade-in-up">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl gradient-primary shadow-lg glow-md animate-float">
            <KeyRound className="h-7 w-7 text-primary-foreground" />
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight">
            {resetDone ? "All Done" : resetToken ? "Set New Password" : "Reset Password"}
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            {resetDone
              ? "Your password has been reset"
              : resetToken
              ? "Enter your new password"
              : "Enter your email to receive a reset link"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {resetDone ? (
            <div className="space-y-4 text-center">
              <CheckCircle className="h-12 w-12 text-green-500 mx-auto" />
              <p className="text-sm text-muted-foreground">You can now sign in with your new password.</p>
              <Link to="/login">
                <Button className="w-full h-11 gradient-primary text-primary-foreground font-medium">
                  Back to Sign In
                </Button>
              </Link>
            </div>
          ) : resetToken ? (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="new-password" className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  New Password
                </Label>
                <Input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={8}
                  autoFocus
                  className="h-11 bg-muted/50 border-border/50 focus:border-primary/50 focus:glow-sm transition-all"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm-password" className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Confirm Password
                </Label>
                <Input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={8}
                  className="h-11 bg-muted/50 border-border/50 focus:border-primary/50 focus:glow-sm transition-all"
                />
              </div>
              <Button
                type="submit"
                className="w-full h-11 gradient-primary text-primary-foreground font-medium shadow-lg hover:shadow-xl hover:brightness-110 transition-all duration-200"
                disabled={isResetting}
              >
                {isResetting ? (
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                    Resetting…
                  </span>
                ) : (
                  "Reset Password"
                )}
              </Button>
            </form>
          ) : submitted ? (
            <div className="space-y-4 text-center">
              <p className="text-sm text-muted-foreground">
                If an account exists for <strong>{email}</strong>, a reset token has been generated. Check the server logs for the token.
              </p>
              <Link to="/login">
                <Button variant="outline" className="w-full h-11">
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back to Sign In
                </Button>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleRequestReset} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoFocus
                  className="h-11 bg-muted/50 border-border/50 focus:border-primary/50 focus:glow-sm transition-all"
                />
              </div>
              <Button
                type="submit"
                className="w-full h-11 gradient-primary text-primary-foreground font-medium shadow-lg hover:shadow-xl hover:brightness-110 transition-all duration-200"
                disabled={isLoading}
              >
                {isLoading ? (
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                    Sending…
                  </span>
                ) : (
                  "Send Reset Token"
                )}
              </Button>
              <p className="text-center text-sm text-muted-foreground">
                <Link to="/login" className="text-primary hover:underline font-medium">
                  <ArrowLeft className="h-3 w-3 inline mr-1" />
                  Back to Sign In
                </Link>
              </p>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
