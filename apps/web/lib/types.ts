export type SessionStatus =
  | "scheduled"
  | "processing"
  | "ready_for_review"
  | "approved"
  | "failed";

export interface PatientProfile {
  id: string;
  first_name: string;
  last_name: string;
  external_patient_id: string | null;
  birth_date: string | null;
  age: number | null;
  gender: string | null;
  phone: string | null;
  email: string | null;
  address: string | null;
  city: string | null;
  profession: string | null;
  notes: string | null;
  consent_reference: string | null;
  intake_id: string | null;
  signed_form_id: string | null;
}

export interface TherapistProfile {
  id: string;
  full_name: string;
  email: string;
  role: "therapist" | "admin";
  google_account_email: string | null;
  google_oauth_connected: boolean;
  google_oauth_email: string | null;
  microsoft_account_email: string | null;
  microsoft_oauth_connected: boolean;
  microsoft_oauth_email: string | null;
  phone: string | null;
  contact_email: string | null;
  address: string | null;
  profession: string | null;
  profile_photo_path: string | null;
  signature_image_path: string | null;
  template_pdf_path: string | null;
  template_docx_path: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionListItem {
  id: string;
  status: SessionStatus;
  source: string;
  google_meet_space_name?: string | null;
  google_conference_record_name?: string | null;
  calendar_event_id?: string | null;
  session_started_at?: string | null;
  session_ended_at?: string | null;
  created_at: string;
  updated_at: string;
  patient: PatientProfile | null;
  therapist: {
    id: string;
    full_name: string;
    email: string;
  } | null;
}

export interface UpcomingMeeting {
  event_id: string | null;
  title: string;
  description: string | null;
  start_at: string | null;
  end_at: string | null;
  meeting_url: string | null;
  calendar_html_link: string | null;
  linked_session_id: string | null;
  linked_patient_name?: string | null;
  source: "google_calendar" | "internal_demo" | string;
}

export interface GoogleSessionSyncResult {
  status: string;
  created_sessions: number;
  updated_sessions: number;
  processed_transcripts: number;
  skipped_events: number;
}
export interface Draft {
  id: string;
  version: number;
  status: string;
  llm_model: string;
  prompt_version: string;
  session_summary: string;
  clinical_profile_text: string;
  structured_json: Record<string, unknown>;
  therapist_review_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail extends SessionListItem {
  drafts: Draft[];
  risk_flags: Array<{
    id: string;
    severity: string;
    category: string;
    snippet: string;
    rationale: string;
    created_at: string;
    requires_human_review: boolean;
  }>;
  documents: Array<{
    id: string;
    clinical_draft_id: string;
    google_doc_id: string | null;
    google_doc_url: string | null;
    exported_docx_path: string | null;
    exported_docx_mime_type: string | null;
    exported_pdf_path: string | null;
    exported_pdf_mime_type: string | null;
    status: string;
    created_at: string;
    updated_at: string;
  }>;
  processing_jobs: Array<{
    id: string;
    job_type: string;
    status: string;
    attempts: number;
    error_message: string | null;
    created_at: string;
    updated_at: string;
  }>;
}

export interface TranscriptPayload {
  id: string;
  raw_text: string;
  normalized_text: string;
  deidentified_text: string;
  language_code: string | null;
  segments: Array<{
    sequence_no: number;
    speaker_label: string;
    text: string;
  }>;
}

export interface AuditLogItem {
  id: string;
  action: string;
  entity_type: string;
  created_at: string;
  metadata: Record<string, unknown>;
}


