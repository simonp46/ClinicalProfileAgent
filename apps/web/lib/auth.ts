"use client";

export const ACCESS_TOKEN_STORAGE_KEY = "tmc_access_token";
const CSRF_KEY = "tmc_csrf";
const SESSION_EVENT_NAME = "tmc:session-ended";

export type SessionEndReason = "expired" | "unauthorized" | "logout";

interface SessionEndedDetail {
  reason: SessionEndReason;
}

function decodeBase64Url(value: string): string | null {
  try {
    const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), "=");
    return atob(padded);
  } catch {
    return null;
  }
}

function dispatchSessionEnded(reason: SessionEndReason): void {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(new CustomEvent<SessionEndedDetail>(SESSION_EVENT_NAME, { detail: { reason } }));
}

export function saveAuth(accessToken: string, csrfToken: string): void {
  if (typeof window === "undefined") {
    return;
  }

  localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, accessToken);
  localStorage.setItem(CSRF_KEY, csrfToken);
}

export function clearAuth(): void {
  if (typeof window === "undefined") {
    return;
  }

  localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  localStorage.removeItem(CSRF_KEY);
}

export function endSession(reason: SessionEndReason = "logout"): void {
  clearAuth();
  dispatchSessionEnded(reason);
}

export function getAccessToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
}

export function getCsrfToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(CSRF_KEY);
}

export function getJwtExpiration(accessToken: string | null = getAccessToken()): number | null {
  if (!accessToken) {
    return null;
  }

  const parts = accessToken.split(".");
  if (parts.length < 2) {
    return null;
  }

  const payloadJson = decodeBase64Url(parts[1]);
  if (!payloadJson) {
    return null;
  }

  try {
    const payload = JSON.parse(payloadJson) as { exp?: number };
    return typeof payload.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

export function isAccessTokenExpired(accessToken: string | null = getAccessToken(), skewMs = 15_000): boolean {
  const expiration = getJwtExpiration(accessToken);
  if (!expiration) {
    return !accessToken;
  }
  return Date.now() >= expiration - skewMs;
}

export function redirectToLogin(reason: SessionEndReason = "expired"): void {
  if (typeof window === "undefined") {
    return;
  }

  const params = new URLSearchParams({ reason });
  window.location.replace(`/login?${params.toString()}`);
}

export function getSessionEndedEventName(): string {
  return SESSION_EVENT_NAME;
}
