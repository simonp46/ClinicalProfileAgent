"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { SessionCard } from "@/components/session-card";
import { listSessions, listUpcomingMeetings, syncGoogleSessions } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { SessionListItem, UpcomingMeeting } from "@/lib/types";

export default function SessionsPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [upcomingMeetings, setUpcomingMeetings] = useState<UpcomingMeeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [meetingsError, setMeetingsError] = useState<string | null>(null);
  const [syncNotice, setSyncNotice] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.replace("/login");
      return;
    }

    void refreshDashboard({ initialLoad: true });
  }, [router]);

  async function refreshDashboard(options: { initialLoad?: boolean } = {}): Promise<void> {
    if (options.initialLoad) {
      setLoading(true);
    } else {
      setSyncing(true);
    }

    setError(null);
    setMeetingsError(null);

    try {
      const syncResult = await syncGoogleSessions().catch(() => null);
      if (syncResult) {
        const changes = syncResult.created_sessions + syncResult.updated_sessions + syncResult.processed_transcripts;
        if (changes > 0) {
          setSyncNotice(
            `Google sincronizado: ${syncResult.created_sessions} sesiones creadas, ${syncResult.updated_sessions} actualizadas y ${syncResult.processed_transcripts} transcripciones procesadas.`,
          );
        }
      }

      const [sessionsResult, meetingsResult] = await Promise.allSettled([listSessions(), listUpcomingMeetings()]);

      if (sessionsResult.status === "fulfilled") {
        setSessions(sessionsResult.value);
      } else {
        setError(sessionsResult.reason instanceof Error ? sessionsResult.reason.message : "No se pudieron cargar sesiones");
      }

      if (meetingsResult.status === "fulfilled") {
        setUpcomingMeetings(meetingsResult.value);
      } else {
        setMeetingsError(
          meetingsResult.reason instanceof Error
            ? meetingsResult.reason.message
            : "No se pudieron cargar las proximas reuniones",
        );
      }
    } finally {
      setLoading(false);
      setSyncing(false);
    }
  }

  return (
    <main className="space-y-4">
      <header className="rounded-2xl border border-brand-200 bg-white/90 p-4 shadow-panel sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink sm:text-2xl">Sesiones clinicas</h1>
            <p className="max-w-2xl text-sm leading-6 text-slate-600">
              Tranqui, tomate un respiro. Revisa proximas reuniones, transcripciones y borradores con una vista mas comoda en movil, tablet y escritorio.
            </p>
          </div>
          <button
            className="w-full rounded-xl border border-brand-200 bg-white px-3 py-2 text-sm font-medium text-ink transition hover:bg-brand-50 sm:w-auto"
            disabled={syncing}
            onClick={() => void refreshDashboard()}
          >
            {syncing ? "Sincronizando..." : "Sincronizar Google"}
          </button>
        </div>
      </header>

      {loading ? <p className="px-1 text-sm text-slate-600">Cargando...</p> : null}
      {error ? <p className="rounded-xl bg-rose-50 p-3 text-sm text-alert">{error}</p> : null}
      {syncNotice ? <p className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">{syncNotice}</p> : null}

      <section className="rounded-2xl border border-brand-200 bg-white/95 p-4 shadow-panel sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-ink">Proximas reuniones o consultas</h2>
            <p className="text-sm leading-6 text-slate-600">
              Visualiza la agenda mas cercana con el titulo del evento y su descripcion cuando este disponible.
            </p>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              Si terminaste una videollamada real y aun no ves la nueva sesion, usa sincronizar Google para importar la reunion, buscar su conference record y procesar la transcripcion disponible.
            </p>
          </div>
          <span className="inline-flex w-fit rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
            {upcomingMeetings.length} programadas
          </span>
        </div>

        {meetingsError ? <p className="mt-3 text-sm text-alert">{meetingsError}</p> : null}

        {upcomingMeetings.length > 0 ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {upcomingMeetings.map((meeting) => {
              const detailHref = meeting.linked_session_id ? `/sessions/${meeting.linked_session_id}` : null;
              const externalHref = meeting.meeting_url ?? meeting.calendar_html_link;

              return (
                <article
                  key={`${meeting.event_id ?? meeting.title}-${meeting.start_at ?? "sin-fecha"}`}
                  className="rounded-2xl border border-brand-100 bg-brand-50/45 p-4"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-xs font-medium uppercase tracking-[0.18em] text-brand-700">
                        {meeting.source === "google_calendar" ? "Google Calendar" : "Agenda demo"}
                      </p>
                      <h3 className="mt-1 text-base font-semibold text-ink">{meeting.title}</h3>
                    </div>
                    <span className="inline-flex w-fit rounded-full border border-brand-200 bg-white px-2.5 py-1 text-xs text-slate-600">
                      {formatMeetingDate(meeting.start_at)}
                    </span>
                  </div>

                  <p className="mt-3 text-sm leading-6 text-slate-700">
                    {meeting.description?.trim() || "Sin descripcion disponible para esta reunion."}
                  </p>

                  <div className="mt-4 flex flex-wrap gap-2 text-xs">
                    {detailHref ? (
                      <Link
                        href={detailHref}
                        className="rounded-full border border-brand-200 bg-white px-3 py-1.5 font-medium text-brand-700 transition hover:border-brand-400"
                      >
                        Abrir sesion vinculada
                      </Link>
                    ) : null}
                    {externalHref ? (
                      <a
                        href={externalHref}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-full border border-brand-200 bg-white px-3 py-1.5 font-medium text-slate-700 transition hover:border-brand-400"
                      >
                        Ver evento
                      </a>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          !loading && (
            <p className="mt-4 rounded-2xl border border-dashed border-brand-200 bg-white/70 p-4 text-sm text-slate-600">
              No hay reuniones proximas programadas por ahora.
            </p>
          )
        )}
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {sessions.map((session) => (
          <SessionCard key={session.id} session={session} />
        ))}
      </section>

      {!loading && sessions.length === 0 ? (
        <p className="rounded-2xl border border-brand-200 bg-white/95 p-5 text-sm text-slate-600 shadow-panel">
          No hay sesiones aun. Ejecuta el seed y demo pipeline para poblar datos.
        </p>
      ) : null}
    </main>
  );
}

function formatMeetingDate(value: string | null): string {
  if (!value) {
    return "Sin fecha";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("es-CO", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
