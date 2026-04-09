"""Create demo sessions for newly registered therapists."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.services.audit_service import AuditService
from app.application.services.clinical_draft_service import ClinicalDraftService
from app.application.services.prompt_registry import PromptRegistry
from app.application.services.session_service import SessionService
from app.application.services.transcript_service import TranscriptService
from app.domain.enums import AuditActorType
from app.domain.models import Session as SessionModel, Therapist
from app.domain.schemas import PatientCreate, SessionCreate, TranscriptIngestRequest, TranscriptSegmentIn
from app.infrastructure.adapters.openai_adapter import MockLLMAdapter


class DemoOnboardingService:
    """Bootstrap demo data so a new therapist can explore the app immediately."""

    MIN_DEMO_SESSIONS = 3

    def __init__(self, db: Session) -> None:
        self.db = db
        self.session_service = SessionService(db)
        self.transcript_service = TranscriptService(db)
        self.prompt_registry = PromptRegistry(db)
        self.audit = AuditService(db)
        self.fixture_path = Path(__file__).resolve().parents[3] / "fixtures" / "sample_transcript.json"

    def ensure_demo_sessions_for_therapist(self, therapist: Therapist) -> list[str]:
        existing_sessions = list(
            self.db.scalars(select(SessionModel).where(SessionModel.therapist_id == therapist.id)).all()
        )

        remaining = self.MIN_DEMO_SESSIONS - len(existing_sessions)
        if remaining <= 0:
            return []

        self.prompt_registry.ensure_seeded(["clinical_draft"])
        draft_service = ClinicalDraftService(self.db, llm_adapter=MockLLMAdapter())

        created_session_ids: list[str] = []
        for index in range(remaining):
            ordinal = len(existing_sessions) + index + 1
            session = self._create_demo_session(therapist, ordinal=ordinal)
            transcript_payload = self._build_transcript_payload(ordinal=ordinal)
            self.transcript_service.ingest_transcript(session, transcript_payload)
            draft_service.generate_for_session(session, regenerate=False)
            created_session_ids.append(session.id)

        self.audit.log(
            actor_type=AuditActorType.system,
            entity_type="therapist",
            entity_id=therapist.id,
            action="demo.sessions_seeded",
            metadata={"therapist_id": therapist.id, "created_sessions": len(created_session_ids)},
        )
        return created_session_ids

    def _create_demo_session(self, therapist: Therapist, *, ordinal: int) -> SessionModel:
        names = [
            ("Ana", "Rojas"),
            ("Carlos", "Mendez"),
            ("Luisa", "Herrera"),
            ("Miguel", "Ortega"),
            ("Paula", "Jimenez"),
        ]
        first_name, last_name = names[(ordinal - 1) % len(names)]

        ended_at = datetime.now(UTC) - timedelta(days=ordinal)
        started_at = ended_at - timedelta(minutes=55)

        payload = SessionCreate(
            therapist_id=therapist.id,
            patient=PatientCreate(
                external_patient_id=f"DEMO-{therapist.id[:6]}-{ordinal:02d}",
                first_name=first_name,
                last_name=last_name,
                phone=f"+57 300000{ordinal:03d}",
                email=f"demo.paciente{ordinal}@example.com",
                gender="femenino" if ordinal % 2 else "masculino",
                age=32 + ordinal,
                profession="Docente" if ordinal % 2 else "Ingeniero",
                address=f"Calle {10 + ordinal} # {20 + ordinal}-3{ordinal}, Bogota",
                consent_reference=f"DEMO-CONSENT-{ordinal:02d}",
                intake_id=f"DEMO-INTAKE-{ordinal:02d}",
                signed_form_id=f"DEMO-FORM-{ordinal:02d}",
            ),
            google_meet_space_name=f"spaces/demo-{therapist.id[:6]}-{ordinal:02d}",
            google_conference_record_name=f"conferenceRecords/demo-{therapist.id[:6]}-{ordinal:02d}",
            session_started_at=started_at,
            session_ended_at=ended_at,
        )
        return self.session_service.create_session(payload)

    def _build_transcript_payload(self, *, ordinal: int) -> TranscriptIngestRequest:
        scenario_segments = self._scenario_segments(ordinal)
        if not scenario_segments:
            fixture = self._load_fixture()
            scenario_segments = fixture.get("segments", [])

        start_base = datetime.now(UTC) - timedelta(days=ordinal, minutes=75)
        segments: list[TranscriptSegmentIn] = []

        for idx, item in enumerate(scenario_segments):
            sequence_no = idx + 1
            started_at = start_base + timedelta(seconds=sequence_no * 24)
            ended_at = started_at + timedelta(seconds=18)

            segments.append(
                TranscriptSegmentIn(
                    speaker_label=str(item.get("speaker_label", "UNKNOWN")),
                    original_participant_ref=item.get("original_participant_ref"),
                    text=str(item.get("text", "")).strip(),
                    start_time=started_at,
                    end_time=ended_at,
                    sequence_no=sequence_no,
                )
            )

        return TranscriptIngestRequest(
            google_transcript_name=f"spaces/demo/transcripts/{ordinal:03d}",
            google_docs_uri=f"https://docs.google.com/document/d/mock-demo-{ordinal:03d}",
            language_code="es-CO",
            segments=segments,
        )

    def _scenario_segments(self, ordinal: int) -> list[dict[str, Any]]:
        scenarios: list[list[dict[str, Any]]] = [
            [
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Buenos dias. Iniciamos valoracion de terapia respiratoria. Cual es su motivo principal de consulta?",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Refiere tos seca frecuente, disnea al subir dos pisos y fatiga en actividades diarias.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Desde cuando inicio y como evoluciono el cuadro?",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Desde hace cuatro meses. Al inicio era ocasional y en el ultimo mes ha empeorado con esfuerzo.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Presenta flema, sibilancias, dolor toracico, congestion nasal, ronquidos o apneas durante sueno?",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Flema matutina y sibilancias leves. Niega dolor toracico. Si hay congestion nasal y ronquidos nocturnos.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Que desencadenantes identifica y que tratamientos previos realizo?",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Empeora con polvo y clima frio. Uso salbutamol inhalado y lavados nasales con alivio parcial.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Antecedentes: asma, bronquitis, COVID, cirugias o medicamentos actuales?",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Antecedente de asma infantil y COVID en 2021. Septoplastia hace tres anos. Actualmente loratadina.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Antecedentes familiares relevantes?",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Madre con asma y padre con alergias respiratorias.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Se registra saturacion O2 de 90 en test de caminata, FC 106 y tolerancia al ejercicio disminuida.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Impresion: patron respiratorio disfuncional. Plan: respiracion diafragmatica, higiene bronquial y seguimiento semanal.",
                },
            ],
            [
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Iniciamos control de terapia respiratoria. Describa motivo de consulta actual.",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Refiere disnea de esfuerzo, congestion nasal persistente y despertares nocturnos por ronquido.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Cuando iniciaron los sintomas y cual ha sido la evolucion?",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Inicio hace seis meses. Empeora en semanas de alta carga laboral y mala calidad de sueno.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Revise checklist: tos, flema, sibilancias, dolor toracico, apneas o fatiga en ejercicio.",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "No flema ni dolor toracico. Tos ocasional y fatiga al ejercicio. Se reportan apneas segun pareja.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Factores desencadenantes y manejo previo?",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Desencadena el estres y el ejercicio intenso. Realizo ejercicios respiratorios online sin supervision.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Antecedentes personales y familiares respiratorios relevantes.",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Rinitis alergica cronica. Sin cirugias toracicas. Hermano con asma y madre con alergias.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "En consulta: saturacion O2 92, FC 98, test de caminata con disnea grado moderado.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Plan terapeutico: entrenamiento de respiracion nasal, higiene del sueno y seguimiento cada 7 dias.",
                },
            ],
            [
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Cuente como se encuentra desde la ultima consulta de terapia respiratoria.",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Refiere mejoria parcial, persiste tos con flema y disnea leve al caminar rapido.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Se mantiene el inicio previo? hubo cambios o exacerbaciones recientes?",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Sin crisis severas. Empeora en exposicion a humo y durante episodios de estres.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Checklist actual: tos, flema, sibilancias, dolor toracico, congestion nasal, ronquidos, apneas, fatiga.",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Tos y flema presentes. Niega dolor toracico. Congestion nasal ocasional, sin apneas referidas.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Tratamientos previos y adherencia a ejercicios en casa?",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Mantiene inhalador segun necesidad y ejercicios diafragmaticos cinco dias por semana.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Antecedentes y comorbilidades actuales?",
                },
                {
                    "speaker_label": "Paciente",
                    "original_participant_ref": "users/patient",
                    "text": "Bronquitis recurrente en infancia y alergias estacionales. Sin antecedentes cardiovasculares conocidos.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Pruebas de hoy: saturacion O2 93 en reposo, FC 94, prueba de control de CO2 sin eventos de alarma.",
                },
                {
                    "speaker_label": "Terapeuta",
                    "original_participant_ref": "users/therapist",
                    "text": "Impresion: compromiso respiratorio leve con progreso parcial. Plan: continuar ejercicios y control en dos semanas.",
                },
            ],
        ]
        return scenarios[(ordinal - 1) % len(scenarios)]

    def _load_fixture(self) -> dict[str, Any]:
        if not self.fixture_path.exists():
            raise FileNotFoundError(f"Fixture transcript not found: {self.fixture_path}")
        return json.loads(self.fixture_path.read_text(encoding="utf-8-sig"))

