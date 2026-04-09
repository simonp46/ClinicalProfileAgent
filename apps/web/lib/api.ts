"use client";

import { endSession, getAccessToken } from "@/lib/auth";
import type {
  AuditLogItem,
  GoogleSessionSyncResult,
  SessionDetail,
  SessionListItem,
  TherapistProfile,
  TranscriptPayload,
  UpcomingMeeting,
} from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function handleFailedResponse(response: Response, path: string): Promise<never> {
  const body = await response.text();

  if (response.status === 401 && !path.startsWith("/api/v1/auth/login") && !path.startsWith("/api/v1/auth/register")) {
    endSession("unauthorized");
  }

  throw new Error(body || `Request failed: ${response.status}`);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers ?? {});

  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    return handleFailedResponse(response, path);
  }
  return (await response.json()) as T;
}

async function requestBlob(path: string): Promise<Blob> {
  const token = getAccessToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: "GET",
    headers,
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    return handleFailedResponse(response, path);
  }
  return response.blob();
}

export async function login(email: string, password: string): Promise<{ access_token: string; csrf_token: string }> {
  return request<{ access_token: string; csrf_token: string }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(payload: {
  full_name: string;
  email: string;
  password: string;
  google_account_email?: string;
}): Promise<{ access_token: string; csrf_token: string }> {
  return request<{ access_token: string; csrf_token: string }>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logout(): Promise<void> {
  await request("/api/v1/auth/logout", {
    method: "POST",
  });
}

export async function getMyProfile(): Promise<TherapistProfile> {
  return request<TherapistProfile>("/api/v1/profile/me");
}

export async function updateMyProfile(payload: {
  full_name?: string | null;
  google_account_email?: string | null;
  phone?: string | null;
  contact_email?: string | null;
  address?: string | null;
  profession?: string | null;
}): Promise<TherapistProfile> {
  return request<TherapistProfile>("/api/v1/profile/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function getGoogleAuthorizationUrl(): Promise<string> {
  const data = await request<{ authorization_url: string }>("/api/v1/profile/me/google/connect", {
    method: "POST",
  });
  return data.authorization_url;
}

export async function disconnectGoogleAccount(): Promise<TherapistProfile> {
  return request<TherapistProfile>("/api/v1/profile/me/google/disconnect", {
    method: "POST",
  });
}

export async function getMicrosoftAuthorizationUrl(): Promise<string> {
  const data = await request<{ authorization_url: string }>("/api/v1/profile/me/microsoft/connect", {
    method: "POST",
  });
  return data.authorization_url;
}

export async function disconnectMicrosoftAccount(): Promise<TherapistProfile> {
  return request<TherapistProfile>("/api/v1/profile/me/microsoft/disconnect", {
    method: "POST",
  });
}

export async function uploadProfileAsset(
  asset: "photo" | "signature" | "template",
  file: File,
): Promise<TherapistProfile> {
  const formData = new FormData();
  formData.append("file", file);

  return request<TherapistProfile>(`/api/v1/profile/me/${asset}`, {
    method: "POST",
    body: formData,
  });
}

export async function getProfileAssetBlob(
  asset: "photo" | "signature" | "template-pdf" | "template-docx",
): Promise<Blob> {
  return requestBlob(`/api/v1/profile/me/assets/${asset}`);
}

export async function listSessions(): Promise<SessionListItem[]> {
  const data = await request<{ items: SessionListItem[] }>("/api/v1/sessions");
  return data.items;
}

export async function listUpcomingMeetings(): Promise<UpcomingMeeting[]> {
  const data = await request<{ items: UpcomingMeeting[] }>("/api/v1/sessions/upcoming-meetings");
  return data.items;
}

export async function syncGoogleSessions(limit = 20): Promise<GoogleSessionSyncResult> {
  const params = new URLSearchParams({ limit: String(limit) });
  return request<GoogleSessionSyncResult>(`/api/v1/sessions/sync-google?${params.toString()}`, {
    method: "POST",
  });
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const data = await request<{ session: SessionDetail }>(`/api/v1/sessions/${sessionId}`);
  return data.session;
}

export async function getTranscript(sessionId: string): Promise<TranscriptPayload> {
  return request<TranscriptPayload>(`/api/v1/sessions/${sessionId}/transcript`);
}

export async function processSession(sessionId: string): Promise<void> {
  await request(`/api/v1/sessions/${sessionId}/process?sync=true`, { method: "POST" });
}

export async function generateDraft(sessionId: string): Promise<void> {
  await request(`/api/v1/sessions/${sessionId}/generate-draft?sync=true`, { method: "POST" });
}

export async function regenerateDraft(sessionId: string): Promise<void> {
  await request(`/api/v1/sessions/${sessionId}/regenerate-draft?sync=true`, { method: "POST" });
}

export async function approveDraft(
  draftId: string,
  payload: { notes: string; clinical_profile_text: string; session_summary: string },
): Promise<void> {
  await request(`/api/v1/drafts/${draftId}/approve`, {
    method: "POST",
    body: JSON.stringify({
      therapist_review_notes: payload.notes,
      clinical_profile_text: payload.clinical_profile_text,
      session_summary: payload.session_summary,
    }),
  });
}

export async function rejectDraft(
  draftId: string,
  payload: { notes: string; clinical_profile_text: string; session_summary: string },
): Promise<void> {
  await request(`/api/v1/drafts/${draftId}/reject`, {
    method: "POST",
    body: JSON.stringify({
      therapist_review_notes: payload.notes,
      clinical_profile_text: payload.clinical_profile_text,
      session_summary: payload.session_summary,
    }),
  });
}

export async function createGoogleDoc(draftId: string): Promise<{ document_id: string }> {
  return request<{ document_id: string }>(`/api/v1/drafts/${draftId}/create-google-doc`, {
    method: "POST",
  });
}

export async function exportDocx(documentId: string): Promise<void> {
  await request(`/api/v1/documents/${documentId}/export-docx`, { method: "POST" });
}

export async function exportPdf(documentId: string): Promise<void> {
  await request(`/api/v1/documents/${documentId}/export-pdf`, { method: "POST" });
}

export async function deleteGeneratedDocument(documentId: string): Promise<void> {
  await request(`/api/v1/documents/${documentId}`, { method: "DELETE" });
}

export async function getDocumentFileBlob(
  documentId: string,
  format: "pdf" | "docx",
  disposition: "inline" | "attachment",
  refresh = true,
): Promise<Blob> {
  const params = new URLSearchParams({
    format,
    disposition,
    refresh: String(refresh),
  });
  return requestBlob(`/api/v1/documents/${documentId}/file?${params.toString()}`);
}

export async function updateSessionPatient(
  sessionId: string,
  payload: {
    full_name?: string | null;
    external_patient_id?: string | null;
    birth_date?: string | null;
    age?: number | null;
    gender?: string | null;
    phone?: string | null;
    email?: string | null;
    address?: string | null;
    city?: string | null;
    profession?: string | null;
  },
): Promise<void> {
  await request(`/api/v1/sessions/${sessionId}/patient`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function getAuditLogs(entityType: string, entityId: string): Promise<AuditLogItem[]> {
  const params = new URLSearchParams({ entity_type: entityType, entity_id: entityId, limit: "50" });
  const data = await request<{ items: AuditLogItem[] }>(`/api/v1/audit-logs?${params.toString()}`);
  return data.items;
}


