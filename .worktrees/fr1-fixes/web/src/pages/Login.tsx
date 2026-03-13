import { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { LogIn, Sparkles } from "lucide-react";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      toast({
        title: "Login failed",
        description: err instanceof Error ? err.message : "Invalid credentials",
        variant: "destructive",
      });
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
            <Sparkles className="h-7 w-7 text-primary-foreground" />
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight">
            Welcome to <span className="text-gradient">Noa</span>
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            Sign in to your agent console
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
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
            <div className="space-y-2">
              <Label htmlFor="password" className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
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
                  Signing in…
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <LogIn className="h-4 w-4" />
                  Sign in
                </span>
              )}
            </Button>
            <div className="text-center text-sm text-muted-foreground space-y-1">
              <p>
                <Link to="/forgot-password" className="text-primary hover:underline font-medium">
                  Forgot password?
                </Link>
              </p>
              <p>
                Don't have an account?{" "}
                <Link to="/register" className="text-primary hover:underline font-medium">
                  Create one
                </Link>
              </p>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
