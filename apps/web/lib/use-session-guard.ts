"use client";

import { useEffect } from "react";

import {
  ACCESS_TOKEN_STORAGE_KEY,
  endSession,
  getAccessToken,
  getJwtExpiration,
  getSessionEndedEventName,
  isAccessTokenExpired,
  redirectToLogin,
  type SessionEndReason,
} from "@/lib/auth";

export function useSessionGuard(): void {
  useEffect(() => {
    let timeoutId: number | null = null;

    const redirect = (reason: SessionEndReason) => {
      redirectToLogin(reason);
    };

    const expireSession = () => {
      endSession("expired");
      redirect("expired");
    };

    const scheduleExpiry = () => {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
        timeoutId = null;
      }

      const token = getAccessToken();
      if (!token || isAccessTokenExpired(token)) {
        expireSession();
        return;
      }

      const expiration = getJwtExpiration(token);
      if (!expiration) {
        return;
      }

      const delay = Math.max(expiration - Date.now() - 5_000, 0);
      timeoutId = window.setTimeout(expireSession, delay);
    };

    const handleSessionEnded = (event: Event) => {
      const customEvent = event as CustomEvent<{ reason?: SessionEndReason }>;
      redirect(customEvent.detail?.reason ?? "expired");
    };

    const handleStorage = (event: StorageEvent) => {
      if (event.key === ACCESS_TOKEN_STORAGE_KEY && !event.newValue) {
        redirect("logout");
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        scheduleExpiry();
      }
    };

    scheduleExpiry();
    window.addEventListener(getSessionEndedEventName(), handleSessionEnded as EventListener);
    window.addEventListener("storage", handleStorage);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      window.removeEventListener(getSessionEndedEventName(), handleSessionEnded as EventListener);
      window.removeEventListener("storage", handleStorage);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);
}
