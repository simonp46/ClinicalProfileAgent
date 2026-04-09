"use client";

import { useState } from "react";

import { logout } from "@/lib/api";
import { endSession } from "@/lib/auth";

export function LogoutButton({ className = "" }: { className?: string }) {
  const [loading, setLoading] = useState(false);

  async function onLogout(): Promise<void> {
    setLoading(true);
    try {
      await logout();
    } catch {
      // We still clear the local session even if the backend cookie was already gone.
    } finally {
      endSession("logout");
      setLoading(false);
    }
  }

  return (
    <button className={className} disabled={loading} onClick={() => void onLogout()}>
      {loading ? "Cerrando..." : "Cerrar sesion"}
    </button>
  );
}
