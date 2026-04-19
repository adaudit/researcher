"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { auth } from "@/lib/api";

export default function AuthPage() {
  const router = useRouter();
  const setAuth = useAuth((s) => s.setAuth);
  const [isSignup, setIsSignup] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      if (isSignup) {
        const res = await auth.signup({ email, password, full_name: fullName, workspace_name: workspaceName });
        setAuth(res.access_token, res.user_id, res.default_workspace_id!);
        router.push("/onboarding");
      } else {
        const res = await auth.login({ email, password });
        setAuth(res.access_token, res.user_id, res.default_workspace_id || "");
        router.push("/dashboard");
      }
    } catch (err: any) {
      setError(err.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-3xl font-bold">Researcher</CardTitle>
          <CardDescription>Creative Intelligence Platform</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {isSignup && (
              <>
                <Input placeholder="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
                <Input placeholder="Workspace name" value={workspaceName} onChange={(e) => setWorkspaceName(e.target.value)} required />
              </>
            )}
            <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />

            {error && <p className="text-sm text-destructive">{error}</p>}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "..." : isSignup ? "Create Account" : "Sign In"}
            </Button>

            <button type="button" className="w-full text-center text-sm text-muted-foreground hover:text-foreground" onClick={() => setIsSignup(!isSignup)}>
              {isSignup ? "Already have an account? Sign in" : "Need an account? Sign up"}
            </button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
