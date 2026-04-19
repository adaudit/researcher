"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/use-auth";

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useAuth((s) => s.token);

  useEffect(() => {
    if (!token) router.replace("/auth");
  }, [token, router]);

  if (!token) return null;

  return <>{children}</>;
}
