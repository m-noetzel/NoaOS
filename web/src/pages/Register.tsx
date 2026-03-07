import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { UserPlus, Sparkles } from "lucide-react";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const { register, isLoading } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      toast({
        title: "Passwords don't match",
        description: "Please make sure both passwords are identical.",
        variant: "destructive",
      });
      return;
    }

    if (password.length < 8) {
      toast({
        title: "Password too short",
        description: "Password must be at least 8 characters.",
        variant: "destructive",
      });
      return;
    }

    try {
      await register(email, password);
      navigate("/", { replace: true });
    } catch (err) {
      toast({
        title: "Registration failed",
        description: err instanceof Error ? err.message : "Could not create account",
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
            Create your <span className="text-gradient">Noa</span> account
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            Set up your personal AI agent
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
                placeholder="Min. 8 characters"
                required
                minLength={8}
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
                placeholder="Repeat password"
                required
                minLength={8}
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
                  Creating account...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <UserPlus className="h-4 w-4" />
                  Create account
                </span>
              )}
            </Button>
            <p className="text-center text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link to="/login" className="text-primary hover:underline font-medium">
                Sign in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
