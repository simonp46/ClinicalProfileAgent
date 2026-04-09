import Link from "next/link";

import { StatusBadge } from "@/components/status-badge";
import type { SessionListItem } from "@/lib/types";

interface SessionCardProps {
  session: SessionListItem;
}

export function SessionCard({ session }: SessionCardProps) {
  const patient = session.patient;

  return (
    <Link
      href={`/sessions/${session.id}`}
      className="block rounded-2xl border border-brand-200 bg-white/95 p-4 shadow-panel transition hover:-translate-y-0.5 hover:border-brand-400"
    >
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">
          {patient ? `${patient.first_name} ${patient.last_name}` : "Paciente sin datos"}
        </h3>
        <StatusBadge value={session.status} />
      </div>
      <p className="text-xs text-slate-600">Sesion: {session.id}</p>
      <p className="text-xs text-slate-600">Consentimiento: {patient?.consent_reference ?? "N/A"}</p>
      <p className="mt-2 text-xs text-slate-500">Actualizado: {new Date(session.updated_at).toLocaleString("es-CO")}</p>
    </Link>
  );
}
