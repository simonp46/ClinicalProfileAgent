"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Panel } from "@/components/panel";
import { StatusBadge } from "@/components/status-badge";
import {
  approveDraft,
  createGoogleDoc,
  deleteGeneratedDocument,
  generateDraft,
  getAuditLogs,
  getDocumentFileBlob,
  getSession,
  getTranscript,
  processSession,
  regenerateDraft,
  rejectDraft,
  updateSessionPatient,
} from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { AuditLogItem, SessionDetail, TranscriptPayload } from "@/lib/types";

type ActionOutcome =
  | { kind: "pending" }
  | { kind: "success"; message: string }
  | { kind: "error"; message: string };

export default function SessionDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const sessionId = params.id;

  const [session, setSession] = useState<SessionDetail | null>(null);
  const [transcript, setTranscript] = useState<TranscriptPayload | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [reviewNotes, setReviewNotes] = useState("");
  const [editedProfile, setEditedProfile] = useState("");
  const [editedSummary, setEditedSummary] = useState("");
  const [patientFullName, setPatientFullName] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [patientIdentification, setPatientIdentification] = useState("");
  const [patientBirthDate, setPatientBirthDate] = useState("");
  const [patientAge, setPatientAge] = useState("");
  const [patientGender, setPatientGender] = useState("");
  const [patientAddress, setPatientAddress] = useState("");
  const [patientCity, setPatientCity] = useState("");
  const [patientProfession, setPatientProfession] = useState("");
  const [patientEmail, setPatientEmail] = useState("");
  const [activeTab, setActiveTab] = useState<"raw" | "normalized" | "deid">("deid");
  const [showProcessedData, setShowProcessedData] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const latestDraft = useMemo(() => session?.drafts?.[0] ?? null, [session]);
  const sortedDocuments = useMemo(
    () => [...(session?.documents ?? [])].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)),
    [session?.documents],
  );

  useEffect(() => {
    if (latestDraft) {
      setEditedProfile(latestDraft.clinical_profile_text);
      setEditedSummary(latestDraft.session_summary);
    }
  }, [latestDraft]);

  useEffect(() => {
    if (!session?.patient) {
      return;
    }

    const fullName = `${session.patient.first_name ?? ""} ${session.patient.last_name ?? ""}`.trim();
    setPatientFullName(fullName);
    setPatientPhone(session.patient.phone ?? "");
    setPatientIdentification(session.patient.external_patient_id ?? "");
    setPatientBirthDate(session.patient.birth_date ?? "");
    setPatientAge(session.patient.age !== null && session.patient.age !== undefined ? String(session.patient.age) : "");
    setPatientGender(session.patient.gender ?? "");
    setPatientAddress(session.patient.address ?? "");
    setPatientCity(session.patient.city ?? "");
    setPatientProfession(session.patient.profession ?? "");
    setPatientEmail(session.patient.email ?? "");
  }, [session]);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    const run = async () => {
      setLoading(true);
      setError(null);
      try {
        const [sessionData, transcriptData, logs] = await Promise.all([
          getSession(sessionId),
          getTranscript(sessionId).catch(() => null),
          getAuditLogs("session", sessionId),
        ]);
        setSession(sessionData);
        setTranscript(transcriptData);
        setAuditLogs(logs);
      } catch (err) {
        setError(err instanceof Error ? err.message : "No se pudo cargar la sesion");
      } finally {
        setLoading(false);
      }
    };

    void run();
  }, [router, sessionId]);

  function getLatestJob(sessionData: SessionDetail | null, jobType: string) {
    if (!sessionData) {
      return null;
    }
    return (
      [...sessionData.processing_jobs]
        .filter((job) => job.job_type === jobType)
        .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0] ?? null
    );
  }

  function getJobCount(sessionData: SessionDetail | null, jobType: string) {
    if (!sessionData) {
      return 0;
    }
    return sessionData.processing_jobs.filter((job) => job.job_type === jobType).length;
  }

  async function refreshAll() {
    const [sessionResult, transcriptResult, logsResult] = await Promise.allSettled([
      getSession(sessionId),
      getTranscript(sessionId).catch(() => null),
      getAuditLogs("session", sessionId),
    ]);

    if (sessionResult.status !== "fulfilled") {
      throw sessionResult.reason;
    }

    const nextSession = sessionResult.value;
    const nextTranscript = transcriptResult.status === "fulfilled" ? transcriptResult.value : null;
    const nextAuditLogs = logsResult.status === "fulfilled" ? logsResult.value : [];

    setSession(nextSession);
    setTranscript(nextTranscript);
    setAuditLogs(nextAuditLogs);

    return {
      session: nextSession,
      transcript: nextTranscript,
      auditLogs: nextAuditLogs,
    };
  }


  async function runAction(
    fn: () => Promise<unknown>,
    options?: {
      pendingMessage?: string;
      successMessage?: string;
      errorMessage?: string;
      pollResolver?: (payload: { session: SessionDetail; transcript: TranscriptPayload | null }) => ActionOutcome;
      pollAttempts?: number;
      pollIntervalMs?: number;
      timeoutMessage?: string;
    },
  ) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (options?.pendingMessage) {
        setNotice(options.pendingMessage);
      }

      await fn();
      const refreshed = await refreshAll();

      if (options?.pollResolver) {
        const immediateOutcome = options.pollResolver({
          session: refreshed.session,
          transcript: refreshed.transcript,
        });

        if (immediateOutcome.kind === "success") {
          setNotice(immediateOutcome.message);
          return;
        }

        if (immediateOutcome.kind === "error") {
          throw new Error(immediateOutcome.message);
        }

        const attempts = options.pollAttempts ?? 6;
        const intervalMs = options.pollIntervalMs ?? 2500;

        for (let attempt = 0; attempt < attempts; attempt += 1) {
          await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
          const next = await refreshAll();
          const outcome = options.pollResolver({
            session: next.session,
            transcript: next.transcript,
          });

          if (outcome.kind === "success") {
            setNotice(outcome.message);
            return;
          }

          if (outcome.kind === "error") {
            throw new Error(outcome.message);
          }
        }

        setNotice(options.timeoutMessage ?? "La accion sigue en proceso. Refresca la sesion en unos segundos.");
        return;
      }

      if (options?.successMessage) {
        setNotice(options.successMessage);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : options?.errorMessage ?? "Accion fallida");
    } finally {
      setBusy(false);
    }
  }

  async function onCreateDoc() {
    setBusy(true);
    setError(null);
    setNotice("Creando Google Doc...");
    try {
      const baselineDocuments = session?.documents.length ?? 0;
      const freshSession = await getSession(sessionId);
      const draft = freshSession.drafts?.[0] ?? null;
      if (!draft) {
        throw new Error("No hay borrador disponible. Genera o regenera un borrador primero.");
      }
      await createGoogleDoc(draft.id);
      const refreshed = await refreshAll();
      if (refreshed.session.documents.length > baselineDocuments) {
        setNotice("Google Doc creado correctamente.");
        return;
      }
      setNotice("La solicitud finalizo, pero no pudimos confirmar el nuevo documento. Refresca la sesion.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear documento");
    } finally {
      setBusy(false);
    }
  }

  async function onSavePatientData(): Promise<void> {
    await updateSessionPatient(sessionId, {
      full_name: patientFullName || null,
      external_patient_id: patientIdentification || null,
      birth_date: patientBirthDate || null,
      age: patientAge ? Number(patientAge) : null,
      gender: patientGender || null,
      phone: patientPhone || null,
      address: patientAddress || null,
      city: patientCity || null,
      profession: patientProfession || null,
      email: patientEmail || null,
    });
  }

  function triggerBrowserDownload(blob: Blob, fileName: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }


  async function onDownloadPdf(documentId: string): Promise<void> {
    const blob = await getDocumentFileBlob(documentId, "pdf", "attachment");
    triggerBrowserDownload(blob, `clinical-draft-${documentId}.pdf`);
  }


  async function onDeleteDocument(documentId: string): Promise<void> {
    const confirmed = window.confirm("Se eliminara este borrador/documento generado. Deseas continuar?");
    if (!confirmed) {
      return;
    }
    await deleteGeneratedDocument(documentId);
  }

  if (loading) {
    return <main className="p-4 sm:p-6">Cargando sesion...</main>;
  }

  if (!session) {
    return <main className="p-4 sm:p-6">Sesion no encontrada.</main>;
  }

  const transcriptText =
    activeTab === "raw"
      ? transcript?.raw_text
      : activeTab === "normalized"
        ? transcript?.normalized_text
        : transcript?.deidentified_text;

  return (
    <main className="mx-auto max-w-7xl space-y-4 overflow-x-hidden p-4 sm:p-6">
      <header className="rounded-2xl bg-white p-4 shadow-panel sm:p-5">
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <Link href="/sessions" className="text-xs text-slate-500 hover:underline">
              Volver a sesiones
            </Link>
            <h1 className="mt-1 text-xl font-semibold text-ink sm:text-2xl">
              {session.patient?.first_name} {session.patient?.last_name}
            </h1>
            <p className="break-all text-sm text-slate-600">Sesion ID: {session.id}</p>
          </div>
          <StatusBadge value={session.status} />
        </div>

        <div className="grid gap-2 text-xs text-slate-600 sm:grid-cols-2 xl:grid-cols-3">
          <p>Consentimiento: {session.patient?.consent_reference ?? "N/A"}</p>
          <p>Intake: {session.patient?.intake_id ?? "N/A"}</p>
          <p>Terapeuta: {session.therapist?.full_name ?? "N/A"}</p>
        </div>

        <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <button
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            disabled={busy}
            onClick={() => {
              const baselineTranscriptId = transcript?.id ?? null;
              const baselineJobCount = getJobCount(session, "ingest_transcript");
              void runAction(() => processSession(sessionId), {
                pendingMessage: "Procesamiento en cola. El estado se actualizara automaticamente.",
                errorMessage: "No se pudo procesar la transcripcion.",
                timeoutMessage: "La transcripcion sigue procesandose. Refresca la sesion en unos segundos.",
                pollResolver: ({ session: currentSession, transcript: currentTranscript }) => {
                  const latestJob = getLatestJob(currentSession, "ingest_transcript");
                  const hasNewJob = getJobCount(currentSession, "ingest_transcript") > baselineJobCount;

                  if (latestJob?.status === "failed" && hasNewJob) {
                    return {
                      kind: "error",
                      message: latestJob.error_message || "La transcripcion fallo durante el procesamiento.",
                    };
                  }

                  if (
                    (latestJob?.status === "success" && hasNewJob) ||
                    (!!currentTranscript && currentTranscript.id !== baselineTranscriptId)
                  ) {
                    return { kind: "success", message: "Transcripcion procesada correctamente." };
                  }

                  if (currentSession.status === "failed") {
                    return {
                      kind: "error",
                      message: "La sesion quedo en estado fallido durante el procesamiento.",
                    };
                  }

                  return { kind: "pending" };
                },
              });
            }}
          >
            Procesar transcript
          </button>
          <button
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            disabled={busy}
            onClick={() => {
              const baselineDraftCount = session?.drafts.length ?? 0;
              const baselineLatestDraftId = latestDraft?.id ?? null;
              const baselineJobCount = getJobCount(session, "generate_draft");
              void runAction(() => generateDraft(sessionId), {
                pendingMessage: "Generacion de borrador en cola. Actualizando estado...",
                errorMessage: "No se pudo generar el borrador.",
                timeoutMessage: "La generacion del borrador sigue en proceso. Refresca la sesion en unos segundos.",
                pollResolver: ({ session: currentSession }) => {
                  const latestJob = getLatestJob(currentSession, "generate_draft");
                  const hasNewJob = getJobCount(currentSession, "generate_draft") > baselineJobCount;
                  const currentLatestDraft = currentSession.drafts?.[0] ?? null;

                  if (latestJob?.status === "failed" && hasNewJob) {
                    return {
                      kind: "error",
                      message: latestJob.error_message || "La generacion del borrador fallo.",
                    };
                  }

                  if (
                    (latestJob?.status === "success" && hasNewJob) ||
                    currentSession.drafts.length > baselineDraftCount ||
                    (!!currentLatestDraft && currentLatestDraft.id !== baselineLatestDraftId)
                  ) {
                    return { kind: "success", message: "Borrador generado correctamente." };
                  }

                  if (currentSession.status === "failed") {
                    return {
                      kind: "error",
                      message: "La sesion quedo en estado fallido durante la generacion.",
                    };
                  }

                  return { kind: "pending" };
                },
              });
            }}
          >
            Generar borrador
          </button>
          <button
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            disabled={busy}
            onClick={() => {
              const baselineDraftCount = session?.drafts.length ?? 0;
              const baselineLatestDraftId = latestDraft?.id ?? null;
              const baselineLatestVersion = latestDraft?.version ?? 0;
              const baselineJobCount = getJobCount(session, "generate_draft");
              void runAction(() => regenerateDraft(sessionId), {
                pendingMessage: "Regeneracion de borrador en cola. Actualizando estado...",
                errorMessage: "No se pudo regenerar el borrador.",
                timeoutMessage: "La regeneracion sigue en proceso. Refresca la sesion en unos segundos.",
                pollResolver: ({ session: currentSession }) => {
                  const latestJob = getLatestJob(currentSession, "generate_draft");
                  const hasNewJob = getJobCount(currentSession, "generate_draft") > baselineJobCount;
                  const currentLatestDraft = currentSession.drafts?.[0] ?? null;

                  if (latestJob?.status === "failed" && hasNewJob) {
                    return {
                      kind: "error",
                      message: latestJob.error_message || "La regeneracion del borrador fallo.",
                    };
                  }

                  if (
                    (latestJob?.status === "success" && hasNewJob) ||
                    currentSession.drafts.length > baselineDraftCount ||
                    (!!currentLatestDraft &&
                      (currentLatestDraft.id !== baselineLatestDraftId ||
                        currentLatestDraft.version > baselineLatestVersion))
                  ) {
                    return { kind: "success", message: "Borrador regenerado correctamente." };
                  }

                  if (currentSession.status === "failed") {
                    return {
                      kind: "error",
                      message: "La sesion quedo en estado fallido durante la regeneracion.",
                    };
                  }

                  return { kind: "pending" };
                },
              });
            }}
          >
            Regenerar borrador
          </button>
          <button
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            disabled={busy || !latestDraft}
            onClick={onCreateDoc}
          >
            Crear Google Doc
          </button>
        </div>
      </header>

      {error ? <p className="rounded-xl bg-rose-50 p-3 text-sm text-alert">{error}</p> : null}
      {notice ? <p className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">{notice}</p> : null}

      <Panel title="Datos Personales del Paciente">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <label className="text-sm text-slate-700">
            Nombre
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={patientFullName}
              onChange={(event) => setPatientFullName(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700">
            Telefono
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={patientPhone}
              onChange={(event) => setPatientPhone(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700">
            Identificacion
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={patientIdentification}
              onChange={(event) => setPatientIdentification(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700">
            Fecha de nacimiento
            <input
              type="date"
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={patientBirthDate}
              onChange={(event) => setPatientBirthDate(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700">
            Edad
            <input
              type="number"
              min={0}
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={patientAge}
              onChange={(event) => setPatientAge(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700">
            Sexo
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={patientGender}
              onChange={(event) => setPatientGender(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700 xl:col-span-2">
            Direccion
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={patientAddress}
              onChange={(event) => setPatientAddress(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700">
            Ciudad
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={patientCity}
              onChange={(event) => setPatientCity(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700">
            Profesion
            <input
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={patientProfession}
              onChange={(event) => setPatientProfession(event.target.value)}
            />
          </label>
          <label className="text-sm text-slate-700 md:col-span-2 xl:col-span-2">
            Email
            <input
              type="email"
              className="mt-1 w-full rounded-xl border border-slate-300 p-2"
              value={patientEmail}
              onChange={(event) => setPatientEmail(event.target.value)}
            />
          </label>
        </div>
        <div className="mt-3">
          <button
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm sm:w-auto"
            disabled={busy}
            onClick={() =>
              runAction(() => onSavePatientData(), {
                successMessage: "Datos personales guardados correctamente.",
                errorMessage: "No se pudieron guardar los datos personales.",
              })
            }
          >
            Guardar datos personales
          </button>
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Borrador Clinico (Editor)">
          {latestDraft ? (
            <>
              <p className="mb-2 break-words text-xs text-slate-500">
                Version {latestDraft.version} | Modelo {latestDraft.llm_model} | Prompt {latestDraft.prompt_version}
              </p>
              <textarea
                className="mb-2 h-24 w-full rounded-xl border border-slate-300 p-3 text-sm"
                value={editedSummary}
                onChange={(event) => setEditedSummary(event.target.value)}
                placeholder="Resumen de sesion"
              />
              <textarea
                className="h-48 w-full rounded-xl border border-slate-300 p-3 text-sm sm:h-56"
                value={editedProfile}
                onChange={(event) => setEditedProfile(event.target.value)}
              />
              <textarea
                className="mt-2 h-24 w-full rounded-xl border border-slate-300 p-3 text-sm"
                placeholder="Notas de revision del terapeuta"
                value={reviewNotes}
                onChange={(event) => setReviewNotes(event.target.value)}
              />
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <button
                  className="rounded bg-safe px-3 py-2 text-sm text-white"
                  disabled={busy}
                  onClick={() =>
                    runAction(
                      () =>
                        approveDraft(latestDraft.id, {
                          notes: reviewNotes,
                          clinical_profile_text: editedProfile,
                          session_summary: editedSummary,
                        }),
                      {
                        successMessage: "Borrador aprobado correctamente.",
                        errorMessage: "No se pudo aprobar el borrador.",
                      },
                    )
                  }
                >
                  Aprobar
                </button>
                <button
                  className="rounded bg-alert px-3 py-2 text-sm text-white"
                  disabled={busy}
                  onClick={() =>
                    runAction(
                      () =>
                        rejectDraft(latestDraft.id, {
                          notes: reviewNotes,
                          clinical_profile_text: editedProfile,
                          session_summary: editedSummary,
                        }),
                      {
                        successMessage: "Borrador rechazado correctamente.",
                        errorMessage: "No se pudo rechazar el borrador.",
                      },
                    )
                  }
                >
                  Rechazar
                </button>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-600">Aun no hay borrador generado.</p>
          )}
        </Panel>

        <Panel title="Riesgos y Alertas">
          {session.risk_flags.length > 0 ? (
            <ul className="space-y-2">
              {session.risk_flags.map((flag) => (
                <li key={flag.id} className="rounded-lg border border-slate-200 p-3">
                  <p className="text-xs font-semibold uppercase text-alert">
                    {flag.severity} - {flag.category}
                  </p>
                  <p className="break-words text-sm leading-6">{flag.snippet}</p>
                  <p className="break-words text-xs leading-5 text-slate-600">{flag.rationale}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-600">Sin banderas registradas.</p>
          )}
        </Panel>

        <div className="xl:col-span-2">
          <Panel title="Documentos Generados (PDF)">
            {sortedDocuments.length > 0 ? (
              <ul className="space-y-2">
                {sortedDocuments.map((doc) => (
                  <li key={doc.id} className="rounded-lg border border-slate-200 p-3">
                    <p className="break-all text-xs text-slate-500">ID: {doc.id}</p>
                    <p className="text-sm">Estado: {doc.status}</p>
                    {doc.google_doc_url ? (
                      <a className="break-all text-sm text-blue-700 underline" href={doc.google_doc_url}>
                        Abrir documento fuente
                      </a>
                    ) : null}
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      <button
                        className="rounded border border-slate-300 px-2 py-2 text-xs"
                        onClick={() =>
                          runAction(() => onDownloadPdf(doc.id), {
                            successMessage: "PDF descargado correctamente.",
                            errorMessage: "No se pudo descargar el PDF.",
                          })
                        }
                      >
                        Descargar PDF
                      </button>
                      <button
                        className="rounded border border-rose-300 px-2 py-2 text-xs text-rose-700"
                        onClick={() =>
                          runAction(() => onDeleteDocument(doc.id), {
                            successMessage: "Documento eliminado correctamente.",
                            errorMessage: "No se pudo eliminar el documento.",
                          })
                        }
                      >
                        Eliminar borrador
                      </button>
                    </div>
                    {doc.exported_pdf_path ? (
                      <p className="mt-1 break-all text-xs text-slate-600">PDF: {doc.exported_pdf_path}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-600">Sin documentos.</p>
            )}
          </Panel>
        </div>

        <section className="overflow-hidden rounded-2xl border border-brand-200 bg-white/95 shadow-panel xl:col-span-2">
          <button
            type="button"
            className="flex w-full items-center justify-between gap-3 p-4 text-left sm:p-5"
            onClick={() => setShowProcessedData((current) => !current)}
          >
            <span className="text-base font-semibold text-ink">Data Procesada</span>
            <span className="text-sm text-slate-500">{showProcessedData ? "Ocultar" : "Mostrar"}</span>
          </button>

          {showProcessedData ? (
            <div className="border-t border-brand-100 p-4 sm:p-5">
              <div className="space-y-4">
                <div>
                  <div className="mb-3 flex flex-wrap gap-2">
                    <button
                      className={`rounded px-2 py-1 text-xs ${activeTab === "raw" ? "bg-slate-900 text-white" : "hover:bg-slate-100"}`}
                      onClick={() => setActiveTab("raw")}
                    >
                      Raw
                    </button>
                    <button
                      className={`rounded px-2 py-1 text-xs ${activeTab === "normalized" ? "bg-slate-900 text-white" : "hover:bg-slate-100"}`}
                      onClick={() => setActiveTab("normalized")}
                    >
                      Normalizado
                    </button>
                    <button
                      className={`rounded px-2 py-1 text-xs ${activeTab === "deid" ? "bg-slate-900 text-white" : "hover:bg-slate-100"}`}
                      onClick={() => setActiveTab("deid")}
                    >
                      Desidentificado
                    </button>
                  </div>
                  <h3 className="mb-2 text-sm font-semibold text-ink">Transcript</h3>
                  <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-xs leading-6">
                    {transcriptText || "Sin transcript"}
                  </pre>
                </div>

                <div>
                  <h3 className="mb-2 text-sm font-semibold text-ink">JSON Estructurado</h3>
                  {latestDraft ? (
                    <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-3 text-xs leading-6">
                      {JSON.stringify(latestDraft.structured_json, null, 2)}
                    </pre>
                  ) : (
                    <p className="text-sm text-slate-600">Sin datos.</p>
                  )}
                </div>

                <div>
                  <h3 className="mb-2 text-sm font-semibold text-ink">Trazabilidad / Audit Trail</h3>
                  {auditLogs.length > 0 ? (
                    <ul className="space-y-2">
                      {auditLogs.map((item) => (
                        <li key={item.id} className="rounded-lg border border-slate-200 p-3 text-xs">
                          <p className="break-words font-semibold">{item.action}</p>
                          <p className="text-slate-500">{new Date(item.created_at).toLocaleString("es-CO")}</p>
                          <pre className="mt-1 overflow-auto whitespace-pre-wrap break-words rounded bg-slate-50 p-2 leading-5">
                            {JSON.stringify(item.metadata, null, 2)}
                          </pre>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-slate-600">Sin eventos registrados.</p>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
