"""Template-aware formatting for respiratory clinical profile drafts."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.models import Session as SessionModel, Therapist

try:
    from docx import Document
except Exception:  # pragma: no cover
    Document = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None


class TemplateFormatService:
    """Build profile text in respiratory-clinical format."""

    _DEFAULT_ORDER: list[str] = [
        "datos_personales",
        "identificacion",
        "hpi",
        "antecedentes",
        "checklist",
        "evaluacion",
        "pruebas",
        "impresion",
        "plan",
    ]

    _SECTION_LABELS: dict[str, str] = {
        "datos_personales": "0) Datos Personales del Paciente",
        "identificacion": "1) Datos de identificacion",
        "hpi": "2) Enfermedad actual (HPI)",
        "antecedentes": "3) Antecedentes relevantes",
        "checklist": "4) Sintomas respiratorios actuales (Checklist)",
        "evaluacion": "5) Evaluacion clinica respiratoria",
        "pruebas": "6) Pruebas realizadas en consulta",
        "impresion": "7) Impresion clinica",
        "plan": "8) Plan terapeutico",
    }

    _SYMPTOM_MAP: dict[str, list[str]] = {
        "Tos": ["tos", "toser"],
        "Flema": ["flema", "esputo", "mucosidad"],
        "Disnea": ["disnea", "ahogo", "falta de aire"],
        "Sibilancias": ["sibilancia", "silbido", "silbidos"],
        "Dolor toracico": ["dolor toracico", "dolor en el pecho", "opresion toracica"],
        "Congestion nasal": ["congestion nasal", "nariz tapada", "rinorrea"],
        "Ronquidos": ["ronquido", "ronca", "roncar"],
        "Apneas sueno": ["apnea", "apneas", "pausas respiratorias"],
        "Fatiga ejercicio": ["fatiga al ejercicio", "fatiga de esfuerzo", "intolerancia al ejercicio"],
    }

    def adapt_profile_text(
        self,
        *,
        therapist: Therapist | None,
        session: SessionModel | None,
        structured_output: dict[str, Any],
        fallback_profile_text: str,
        session_summary: str,
        transcript_text: str,
    ) -> str:
        heading_order = self._resolve_heading_order(therapist)

        template_data_raw = structured_output.get("plantilla_historia_clinica_respiratoria")
        template_data = template_data_raw if isinstance(template_data_raw, dict) else {}

        checklist = self._build_symptom_checklist(
            transcript_text,
            template_checklist=template_data.get("sintomas_respiratorios_checklist"),
        )

        section_content = {
            "datos_personales": self._build_personal_data_section(
                session,
                template_personal=template_data.get("datos_personales_paciente"),
            ),
            "identificacion": self._build_identification_section(
                session,
                structured_output,
                template_ident=template_data.get("datos_identificacion"),
            ),
            "hpi": self._build_hpi_section(
                structured_output,
                transcript_text,
                checklist,
                session_summary,
                template_hpi=template_data.get("enfermedad_actual_hpi"),
            ),
            "antecedentes": self._build_antecedentes_section(
                structured_output,
                transcript_text,
                template_antecedentes=template_data.get("antecedentes_relevantes"),
            ),
            "checklist": self._format_checklist(checklist),
            "evaluacion": self._build_evaluacion_section(
                structured_output,
                transcript_text,
                checklist,
                template_evaluacion=template_data.get("evaluacion_clinica_respiratoria"),
            ),
            "pruebas": self._build_pruebas_section(
                transcript_text,
                template_pruebas=template_data.get("pruebas_realizadas_en_consulta"),
            ),
            "impresion": self._build_impresion_section(
                structured_output,
                checklist,
                session_summary,
                template_impresion=template_data.get("impresion_clinica"),
            ),
            "plan": self._build_plan_section(
                structured_output,
                transcript_text,
                template_plan=template_data.get("plan_terapeutico"),
            ),
        }

        blocks: list[str] = []
        for key in heading_order:
            label = self._SECTION_LABELS.get(key)
            if not label:
                continue
            blocks.append(f"{label}\n{section_content.get(key, 'No referido')}")

        if not blocks:
            return fallback_profile_text
        return "\n\n".join(blocks)

    def _build_personal_data_section(
        self,
        session: SessionModel | None,
        *,
        template_personal: Any,
    ) -> str:
        template = template_personal if isinstance(template_personal, dict) else {}

        if session is None or session.patient is None:
            return "\n".join(
                [
                    f"- Nombre: {self._not_referido(template.get('nombre_paciente'))}",
                    f"- Telefono: {self._not_referido(template.get('telefono'))}",
                    f"- Identificacion: {self._not_referido(template.get('identificacion'))}",
                    f"- Fecha de nacimiento: {self._not_referido(template.get('fecha_nacimiento'))}",
                    f"- Direccion: {self._not_referido(template.get('direccion'))}",
                    f"- Ciudad: {self._not_referido(template.get('ciudad'))}",
                    f"- Profesion: {self._not_referido(template.get('profesion'))}",
                    f"- Email: {self._not_referido(template.get('email'))}",
                ]
            )

        patient = session.patient
        full_name = f"{patient.first_name} {patient.last_name}".strip()
        city_value = self._first_meaningful(patient.city, template.get("ciudad"))
        return "\n".join(
            [
                f"- Nombre: {self._not_referido(self._first_meaningful(full_name, template.get('nombre_paciente')))}",
                f"- Telefono: {self._not_referido(self._first_meaningful(patient.phone, template.get('telefono')))}",
                f"- Identificacion: {self._not_referido(self._first_meaningful(patient.external_patient_id, template.get('identificacion')))}",
                f"- Fecha de nacimiento: {self._not_referido(self._first_meaningful(patient.birth_date, template.get('fecha_nacimiento')))}",
                f"- Direccion: {self._not_referido(self._first_meaningful(patient.address, template.get('direccion')))}",
                f"- Ciudad: {self._not_referido(city_value)}",
                f"- Profesion: {self._not_referido(self._first_meaningful(patient.profession, template.get('profesion')))}",
                f"- Email: {self._not_referido(self._first_meaningful(patient.email, template.get('email')))}",
            ]
        )

    def _build_identification_section(
        self,
        session: SessionModel | None,
        structured_output: dict[str, Any],
        *,
        template_ident: Any,
    ) -> str:
        ident_data = structured_output.get("identificacion_minima")
        ident = ident_data if isinstance(ident_data, dict) else {}
        template = template_ident if isinstance(template_ident, dict) else {}

        patient_name: Any = None
        age: Any = None
        sex: Any = None
        fecha: Any = None

        if session is not None and session.patient is not None:
            full_name = f"{session.patient.first_name} {session.patient.last_name}".strip()
            patient_name = self._first_meaningful(full_name)
            age = self._first_meaningful(session.patient.age)
            sex = self._first_meaningful(session.patient.gender)
            date_source = session.session_ended_at or session.session_started_at
            if isinstance(date_source, datetime):
                fecha = date_source.strftime("%d/%m/%Y")

        patient_name = self._not_referido(
            self._first_meaningful(template.get("nombre_paciente"), patient_name, ident.get("nombre_paciente"))
        )
        age = self._not_referido(self._first_meaningful(template.get("edad"), age, ident.get("edad_referida")))
        sex = self._not_referido(self._first_meaningful(template.get("sexo"), sex))
        fecha = self._not_referido(
            self._first_meaningful(template.get("fecha_consulta"), fecha, datetime.now().strftime("%d/%m/%Y"))
        )

        motivo = self._not_referido(
            self._first_meaningful(template.get("motivo_consulta"), structured_output.get("motivo_consulta"))
        )

        lines = [
            f"- Nombre del paciente: {patient_name}",
            f"- Edad: {age}",
            f"- Sexo: {sex}",
            f"- Fecha consulta: {fecha}",
            f"- Motivo de consulta: {motivo}",
        ]
        return "\n".join(lines)

    def _build_hpi_section(
        self,
        structured_output: dict[str, Any],
        transcript_text: str,
        checklist: dict[str, str],
        session_summary: str,
        *,
        template_hpi: Any,
    ) -> str:
        template = template_hpi if isinstance(template_hpi, dict) else {}
        if template:
            return (
                f"Se documenta inicio de sintomas: {self._not_referido(template.get('inicio_sintomas'))}. "
                f"La evolucion reportada es: {self._not_referido(template.get('evolucion'))}. "
                "Los sintomas respiratorios principales son: "
                f"{self._not_referido(template.get('sintomas_principales_respiratorios'))}. "
                f"Factores desencadenantes: {self._not_referido(template.get('factores_desencadenantes'))}. "
                f"Tratamientos previos: {self._not_referido(template.get('tratamientos_previos'))}. "
                f"Estado actual: {self._not_referido(template.get('estado_actual'))}."
            )

        text = transcript_text.lower()
        inicio = self._extract_phrase(text, [r"desde hace[^\.\n]{3,80}", r"inicio[^\.\n]{3,80}", r"comenzo[^\.\n]{3,80}"])
        evolucion = self._extract_phrase(text, [r"ha empeorado[^\.\n]{0,80}", r"ha mejorado[^\.\n]{0,80}", r"evolucion[^\.\n]{0,80}"])
        sintomas_presentes = [label for label, status in checklist.items() if status == "Presente"]
        sintomas = ", ".join(sintomas_presentes) if sintomas_presentes else "No referido"
        desencadenantes = self._to_sentence_list(structured_output.get("factores_estresores_actuales"))
        tratamientos_previos = self._extract_phrase(
            text,
            [r"inhalador[^\.\n]{0,80}", r"nebuliza[^\.\n]{0,80}", r"tratamiento[^\.\n]{0,80}", r"medicamento[^\.\n]{0,80}"],
        )
        estado_actual = self._not_referido(structured_output.get("resumen_sesion") or session_summary)

        return (
            f"Se documenta inicio de sintomas: {self._not_referido(inicio)}. "
            f"La evolucion reportada es: {self._not_referido(evolucion)}. "
            f"Los sintomas respiratorios principales son: {self._not_referido(sintomas)}. "
            f"Factores desencadenantes: {self._not_referido(desencadenantes)}. "
            f"Tratamientos previos: {self._not_referido(tratamientos_previos)}. "
            f"Estado actual: {estado_actual}."
        )

    def _build_antecedentes_section(
        self,
        structured_output: dict[str, Any],
        transcript_text: str,
        *,
        template_antecedentes: Any,
    ) -> str:
        template = template_antecedentes if isinstance(template_antecedentes, dict) else {}
        if template:
            lines = [
                "Personales",
                f"- Respiratorios: {self._not_referido(self._join_list(template.get('personales_respiratorios')))}",
                f"- Cardiovasculares: {self._not_referido(self._join_list(template.get('personales_cardiovasculares')))}",
                f"- Quirurgicos: {self._not_referido(self._join_list(template.get('personales_quirurgicos')))}",
                f"- Medicamentos actuales: {self._not_referido(self._join_list(template.get('medicamentos_actuales')))}",
                "",
                "Familiares",
                f"- Asma: {self._not_referido(self._join_list(template.get('familiares_asma')))}",
                f"- Alergias: {self._not_referido(self._join_list(template.get('familiares_alergias')))}",
                "- Enfermedades pulmonares: "
                f"{self._not_referido(self._join_list(template.get('familiares_enfermedades_pulmonares')))}",
            ]
            return "\n".join(lines)

        lowered = transcript_text.lower()
        antecedentes = self._to_sentence_list(structured_output.get("antecedentes_mencionados"))
        personales_respiratorios = self._collect_mentions(
            lowered,
            ["asma", "bronquitis", "neumonia", "covid", "alergia", "rinitis"],
            fallback_from_structured=antecedentes,
        )
        personales_cardiovasculares = self._collect_mentions(lowered, ["hipertension", "cardiaco", "arritmia", "infarto"])
        personales_quirurgicos = self._collect_mentions(lowered, ["cirugia", "operado", "quirurg"])
        medicamentos = self._collect_mentions(lowered, ["inhalador", "salbutamol", "corticoide", "medicamento", "broncodilatador"])

        familiares_asma = self._family_mention(lowered, "asma")
        familiares_alergias = self._family_mention(lowered, "alerg")
        familiares_pulmonares = self._family_mention(lowered, "pulmon")

        return "\n".join(
            [
                "Personales",
                f"- Respiratorios: {self._not_referido(personales_respiratorios)}",
                f"- Cardiovasculares: {self._not_referido(personales_cardiovasculares)}",
                f"- Quirurgicos: {self._not_referido(personales_quirurgicos)}",
                f"- Medicamentos actuales: {self._not_referido(medicamentos)}",
                "",
                "Familiares",
                f"- Asma: {familiares_asma}",
                f"- Alergias: {familiares_alergias}",
                f"- Enfermedades pulmonares: {familiares_pulmonares}",
            ]
        )

    def _build_symptom_checklist(self, transcript_text: str, *, template_checklist: Any) -> dict[str, str]:
        template = template_checklist if isinstance(template_checklist, dict) else {}
        if template:
            return {
                "Tos": self._normalize_check_status(template.get("tos")),
                "Flema": self._normalize_check_status(template.get("flema")),
                "Disnea": self._normalize_check_status(template.get("disnea")),
                "Sibilancias": self._normalize_check_status(template.get("sibilancias")),
                "Dolor toracico": self._normalize_check_status(template.get("dolor_toracico")),
                "Congestion nasal": self._normalize_check_status(template.get("congestion_nasal")),
                "Ronquidos": self._normalize_check_status(template.get("ronquidos")),
                "Apneas sueno": self._normalize_check_status(template.get("apneas_sueno")),
                "Fatiga ejercicio": self._normalize_check_status(template.get("fatiga_ejercicio")),
            }

        lowered = transcript_text.lower()
        result: dict[str, str] = {}
        for label, terms in self._SYMPTOM_MAP.items():
            result[label] = self._status_for_terms(lowered, terms)
        return result

    def _format_checklist(self, checklist: dict[str, str]) -> str:
        return "\n".join(f"- {label}: {status}" for label, status in checklist.items())

    def _build_evaluacion_section(
        self,
        structured_output: dict[str, Any],
        transcript_text: str,
        checklist: dict[str, str],
        *,
        template_evaluacion: Any,
    ) -> str:
        template = template_evaluacion if isinstance(template_evaluacion, dict) else {}
        if template:
            return "\n".join(
                [
                    "- Patron respiratorio observado: "
                    f"{self._not_referido(template.get('patron_respiratorio_observado'))}",
                    f"- Tipo de respiracion (oral/nasal): {self._not_referido(template.get('tipo_respiracion'))}",
                    f"- Uso de musculos accesorios: {self._not_referido(template.get('uso_musculos_accesorios'))}",
                    f"- Tolerancia al ejercicio: {self._not_referido(template.get('tolerancia_ejercicio'))}",
                    f"- Calidad de la respiracion: {self._not_referido(template.get('calidad_respiracion'))}",
                    "- Hallazgos relevantes mencionados por terapeuta: "
                    f"{self._not_referido(template.get('hallazgos_relevantes_mencionados_por_terapeuta'))}",
                ]
            )

        lowered = transcript_text.lower()
        patron = self._extract_phrase(lowered, [r"patron respiratorio[^\.\n]{0,80}", r"respiracion superficial[^\.\n]{0,80}"])
        tipo = self._extract_phrase(lowered, [r"respiracion oral", r"respiracion nasal"])
        accesorios = self._extract_phrase(lowered, [r"musculos accesorios[^\.\n]{0,80}", r"uso de accesorios[^\.\n]{0,80}"])

        tolerancia = "No referido"
        if checklist.get("Fatiga ejercicio") == "Presente" or checklist.get("Disnea") == "Presente":
            tolerancia = "Disminuida"
        elif checklist.get("Fatiga ejercicio") == "Ausente" and checklist.get("Disnea") == "Ausente":
            tolerancia = "Conservada"

        calidad = self._extract_phrase(lowered, [r"respiracion[^\.\n]{0,80}", r"disnea[^\.\n]{0,80}", r"fatiga[^\.\n]{0,80}"])
        hallazgos = self._to_sentence_list(structured_output.get("frases_textuales_clave"))

        return "\n".join(
            [
                f"- Patron respiratorio observado: {self._not_referido(patron)}",
                f"- Tipo de respiracion (oral/nasal): {self._not_referido(tipo)}",
                f"- Uso de musculos accesorios: {self._not_referido(accesorios)}",
                f"- Tolerancia al ejercicio: {self._not_referido(tolerancia)}",
                f"- Calidad de la respiracion: {self._not_referido(calidad)}",
                f"- Hallazgos relevantes mencionados por terapeuta: {self._not_referido(hallazgos)}",
            ]
        )

    def _build_pruebas_section(self, transcript_text: str, *, template_pruebas: Any) -> str:
        pruebas = self._to_list(template_pruebas)
        if pruebas:
            return "\n".join(f"- {item}" for item in pruebas)

        lowered = transcript_text.lower()
        tests = [
            ("Saturacion O2", ["saturacion", "spo2", "oxigeno"]),
            ("Frecuencia cardiaca", ["frecuencia cardiaca", "fc", "pulso"]),
            ("Test caminata", ["test caminata", "caminata de 6 minutos", "6mw"]),
            ("Test apnea / control CO2", ["apnea", "co2", "capnografia"]),
            ("Incentivo respiratorio", ["incentivo respiratorio", "espirómetro incentivador"]),
            ("Espirometria", ["espirometria", "flujo espiratorio"]),
        ]

        findings = [f"- {label}" for label, terms in tests if any(term in lowered for term in terms)]
        return "\n".join(findings) if findings else "- No referido"

    def _build_impresion_section(
        self,
        structured_output: dict[str, Any],
        checklist: dict[str, str],
        session_summary: str,
        *,
        template_impresion: Any,
    ) -> str:
        if template_impresion:
            return self._not_referido(template_impresion)

        present = [label.lower() for label, status in checklist.items() if status == "Presente"]
        if present:
            sintomas = ", ".join(present)
            return (
                "Paciente con hallazgos compatibles con compromiso respiratorio funcional; "
                f"presenta {sintomas}. Requiere correlacion clinica y seguimiento profesional."
            )

        resumen = self._not_referido(structured_output.get("resumen_sesion") or session_summary)
        if resumen != "No referido":
            return f"Impresion clinica basada en lo referido durante consulta: {resumen}."
        return "No referido"

    def _build_plan_section(
        self,
        structured_output: dict[str, Any],
        transcript_text: str,
        *,
        template_plan: Any,
    ) -> str:
        plan_items = self._to_list(template_plan) or self._to_list(structured_output.get("plan_o_proximos_pasos"))
        lowered = transcript_text.lower()

        tecnicas = [item for item in plan_items if any(t in item.lower() for t in ["respir", "diafrag", "coheren"])]
        frecuencia = self._extract_phrase(lowered, [r"\d+\s+sesiones?\s+por\s+semana", r"semanal", r"cada\s+\d+\s+dias"])
        seguimiento = self._extract_phrase(lowered, [r"seguimiento[^\.\n]{0,80}", r"control[^\.\n]{0,80}", r"proxima sesion[^\.\n]{0,80}"])

        if not seguimiento and plan_items:
            seguimiento = "; ".join(plan_items[:2])

        return "\n".join(
            [
                "- Tecnicas respiratorias indicadas: "
                f"{self._not_referido('; '.join(tecnicas) if tecnicas else None)}",
                f"- Frecuencia de sesiones: {self._not_referido(frecuencia)}",
                "- Recomendaciones domiciliarias: "
                f"{self._not_referido('; '.join(plan_items) if plan_items else None)}",
                f"- Seguimiento: {self._not_referido(seguimiento)}",
            ]
        )

    def _resolve_heading_order(self, therapist: Therapist | None) -> list[str]:
        if therapist is None:
            return list(self._DEFAULT_ORDER)

        extracted_lines: list[str] = []
        if therapist.template_docx_path:
            extracted_lines.extend(self._read_docx_lines(therapist.template_docx_path))
        if not extracted_lines and therapist.template_pdf_path:
            extracted_lines.extend(self._read_pdf_lines(therapist.template_pdf_path))

        keys: list[str] = []
        for line in extracted_lines:
            key = self._match_section_key(line)
            if key and key not in keys:
                keys.append(key)

        if len(keys) >= 3:
            return keys
        return list(self._DEFAULT_ORDER)

    def _match_section_key(self, heading: str) -> str | None:
        normalized = self._normalize_text(heading)
        if not normalized:
            return None

        if "datos personales" in normalized or "datos del paciente" in normalized:
            return "datos_personales"
        if "identificacion" in normalized or "datos de identific" in normalized:
            return "identificacion"
        if "motivo de consulta" in normalized or "motivo consulta" in normalized:
            return "identificacion"
        if "hpi" in normalized or "enfermedad actual" in normalized:
            return "hpi"
        if "antecedente" in normalized:
            return "antecedentes"
        if "checklist" in normalized or "sintomas respiratorios" in normalized:
            return "checklist"
        if "evaluacion" in normalized and "respir" in normalized:
            return "evaluacion"
        if "pruebas" in normalized:
            return "pruebas"
        if "impresion" in normalized:
            return "impresion"
        if "plan" in normalized and "terapeut" in normalized:
            return "plan"
        return None

    def _read_docx_lines(self, path: str) -> list[str]:
        if Document is None:
            return []
        docx_path = Path(path)
        if not docx_path.exists():
            return []

        try:
            document = Document(str(docx_path))
        except Exception:
            return []

        lines = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return self._filter_candidate_headings(lines)

    def _read_pdf_lines(self, path: str) -> list[str]:
        if PdfReader is None:
            return []
        pdf_path = Path(path)
        if not pdf_path.exists():
            return []

        try:
            reader = PdfReader(str(pdf_path))
        except Exception:
            return []

        lines: list[str] = []
        for page in reader.pages[:2]:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            lines.extend(item.strip() for item in text.splitlines() if item.strip())

        return self._filter_candidate_headings(lines)

    def _filter_candidate_headings(self, lines: Iterable[str]) -> list[str]:
        candidates: list[str] = []
        for line in lines:
            clean = line.strip()
            if len(clean) < 4 or len(clean) > 120:
                continue
            letters = sum(char.isalpha() for char in clean)
            if letters < 4:
                continue
            if clean.startswith("-"):
                continue
            candidates.append(clean)
        return candidates

    def _normalize_text(self, value: str) -> str:
        lowered = value.lower()
        normalized = unicodedata.normalize("NFKD", lowered)
        ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return " ".join(ascii_only.split())

    def _normalize_check_status(self, value: Any) -> str:
        status = self._normalize_text(str(value or ""))
        if "presen" in status:
            return "Presente"
        if "ausen" in status or status in {"no", "negado", "negada"}:
            return "Ausente"
        return "No mencionado"

    def _status_for_terms(self, text: str, terms: list[str]) -> str:
        for term in terms:
            escaped = re.escape(term)
            if re.search(rf"\b(?:no|niega|sin)\s+(?:presenta\s+)?{escaped}\b", text):
                return "Ausente"
        for term in terms:
            if term in text:
                return "Presente"
        return "No mencionado"

    def _to_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _join_list(self, value: Any) -> str:
        items = self._to_list(value)
        return "; ".join(items) if items else ""

    def _to_sentence_list(self, value: Any) -> str:
        items = self._to_list(value)
        if not items:
            return "No referido"
        return "; ".join(items)

    def _extract_phrase(self, text: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                phrase = match.group(0).strip(" .,;:")
                if phrase:
                    return phrase
        return None

    def _collect_mentions(self, text: str, terms: list[str], *, fallback_from_structured: str | None = None) -> str:
        found = [term for term in terms if term in text]
        if found:
            return ", ".join(dict.fromkeys(found))
        if fallback_from_structured and fallback_from_structured != "No referido":
            return fallback_from_structured
        return "No referido"

    def _family_mention(self, text: str, term_fragment: str) -> str:
        family_markers = ["madre", "padre", "hermano", "hermana", "familia"]
        if term_fragment in text and any(marker in text for marker in family_markers):
            return "Referido"
        return "No referido"

    def _is_meaningful(self, value: Any) -> bool:
        if value is None:
            return False
        cleaned = str(value).strip()
        if not cleaned:
            return False
        lowered = cleaned.lower()
        return lowered not in {"no referido", "no mencionad", "n/a", "na", "none", "null"}

    def _first_meaningful(self, *values: Any) -> Any | None:
        for value in values:
            if self._is_meaningful(value):
                return value
        return None

    def _not_referido(self, value: Any) -> str:
        if not self._is_meaningful(value):
            return "No referido"
        return str(value).strip()



