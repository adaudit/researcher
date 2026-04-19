"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";

export default function Home() {
  const router = useRouter();
  const token = useAuth((s) => s.token);

  useEffect(() => {
    if (token) {
      router.replace("/dashboard");
    } else {
      router.replace("/auth");
    }
  }, [token, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="animate-pulse text-muted-foreground">Loading...</div>
    </div>
  );
}
