"use client";

import { useSessionGuard } from "@/lib/use-session-guard";

export function DashboardSessionShell({ children }: { children: React.ReactNode }) {
  useSessionGuard();
  return <>{children}</>;
}
