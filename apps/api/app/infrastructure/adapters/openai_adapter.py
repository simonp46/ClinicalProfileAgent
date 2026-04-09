"""OpenAI Responses API adapter."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.domain.schemas import ClinicalGenerationResult


class LLMAdapterError(Exception):
    """Raised when model calls fail."""


class BaseLLMAdapter(ABC):
    """Boundary interface for all LLM providers."""

    @abstractmethod
    def generate_clinical_artifacts(self, *, prompt: str, transcript_chunk: str) -> ClinicalGenerationResult:
        raise NotImplementedError


class OpenAIResponsesAdapter(BaseLLMAdapter):
    """OpenAI Responses implementation with JSON validation."""

    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(settings.openai_max_retries),
        reraise=True,
    )
    def generate_clinical_artifacts(self, *, prompt: str, transcript_chunk: str) -> ClinicalGenerationResult:
        try:
            response = self.client.responses.create(
                model=settings.openai_model,
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": prompt}],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "Genera un JSON valido con las llaves: structured_output, "
                                    "session_summary, clinical_profile_text, risk_flags.\n\n"
                                    f"TRANSCRIPCION DESIDENTIFICADA:\n{transcript_chunk}"
                                ),
                            }
                        ],
                    },
                ],
                temperature=0,
                max_output_tokens=3000,
            )
        except Exception as exc:
            raise LLMAdapterError("OpenAI request failed") from exc

        content = getattr(response, "output_text", "")
        if not content:
            raise LLMAdapterError("OpenAI returned empty response")

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMAdapterError("Invalid JSON response from OpenAI") from exc

        try:
            return ClinicalGenerationResult.model_validate(payload)
        except Exception as exc:
            raise LLMAdapterError("ClinicalGenerationResult validation failed") from exc


class MockLLMAdapter(BaseLLMAdapter):
    """Deterministic fallback used for local demo or CI."""

    def generate_clinical_artifacts(self, *, prompt: str, transcript_chunk: str) -> ClinicalGenerationResult:
        _ = prompt
        lowered = transcript_chunk.lower()

        checklist = {
            "tos": self._status_for_terms(lowered, ["tos", "toser"]),
            "flema": self._status_for_terms(lowered, ["flema", "esputo", "mucosidad"]),
            "disnea": self._status_for_terms(lowered, ["disnea", "falta de aire", "ahogo"]),
            "sibilancias": self._status_for_terms(lowered, ["sibilancia", "silbido"]),
            "dolor_toracico": self._status_for_terms(lowered, ["dolor toracico", "dolor en el pecho"]),
            "congestion_nasal": self._status_for_terms(lowered, ["congestion nasal", "nariz tapada"]),
            "ronquidos": self._status_for_terms(lowered, ["ronquido", "ronca", "roncar"]),
            "apneas_sueno": self._status_for_terms(lowered, ["apnea", "apneas", "pausas respiratorias"]),
            "fatiga_ejercicio": self._status_for_terms(
                lowered,
                ["fatiga al ejercicio", "fatiga de esfuerzo", "intolerancia al ejercicio"],
            ),
        }

        symptoms_present = [
            label.replace("_", " ")
            for label, status in checklist.items()
            if status == "Presente"
        ]

        hpi_inicio = self._extract_phrase(
            lowered,
            [
                r"desde hace[^\.\n]{3,90}",
                r"inicio[^\.\n]{3,90}",
                r"comenzo[^\.\n]{3,90}",
            ],
        )
        hpi_evolucion = self._extract_phrase(
            lowered,
            [
                r"ha empeorado[^\.\n]{0,90}",
                r"ha mejorado[^\.\n]{0,90}",
                r"evolucion[^\.\n]{0,90}",
            ],
        )

        desencadenantes = self._collect_items(
            lowered,
            [
                "ejercicio",
                "esfuerzo",
                "humo",
                "polvo",
                "estres",
                "frio",
                "carga laboral",
            ],
        )
        tratamientos_previos = self._collect_items(
            lowered,
            [
                "inhalador",
                "salbutamol",
                "nebulizacion",
                "nebulizador",
                "corticoide",
                "lavado nasal",
            ],
        )

        antecedentes_respiratorios = self._collect_items(
            lowered,
            ["asma", "bronquitis", "neumonia", "covid", "alergia", "rinitis"],
        )
        antecedentes_cardiovasculares = self._collect_items(
            lowered,
            ["hipertension", "taquicardia", "arritmia", "cardiopatia"],
        )
        antecedentes_quirurgicos = self._collect_items(
            lowered,
            ["cirugia", "operado", "septoplastia", "amigdalectomia"],
        )

        pruebas = []
        if self._contains_any(lowered, ["saturacion", "spo2", "o2"]):
            pruebas.append("Saturacion O2")
        if self._contains_any(lowered, ["frecuencia cardiaca", "fc", "pulso"]):
            pruebas.append("Frecuencia cardiaca")
        if self._contains_any(lowered, ["test caminata", "caminata de 6 minutos", "6mw"]):
            pruebas.append("Test caminata")
        if self._contains_any(lowered, ["apnea", "co2", "capnografia"]):
            pruebas.append("Test apnea / control CO2")
        if self._contains_any(lowered, ["incentivo respiratorio", "espirómetro incentivador"]):
            pruebas.append("Incentivo respiratorio")
        if self._contains_any(lowered, ["espirometria", "flujo espiratorio"]):
            pruebas.append("Espirometria")

        risk_mentions: list[str] = []
        risk_flags: list[dict[str, Any]] = []

        if "suicid" in lowered or "quitarme la vida" in lowered:
            risk_mentions.append("Mencion de ideacion suicida que requiere revision clinica inmediata.")
            risk_flags.append(
                {
                    "severity": "critical",
                    "category": "suicide_risk",
                    "snippet": "Referencia a ideacion suicida",
                    "rationale": "El discurso incluye expresiones compatibles con riesgo suicida.",
                    "requires_human_review": True,
                }
            )

        spo2_match = re.search(r"(?:spo2|saturacion)\s*(?:de|en)?\s*(\d{2})", lowered)
        if spo2_match and int(spo2_match.group(1)) < 92:
            risk_mentions.append("Desaturacion reportada durante actividad, requiere seguimiento profesional.")
            risk_flags.append(
                {
                    "severity": "medium",
                    "category": "other",
                    "snippet": f"Saturacion reportada en {spo2_match.group(1)}%",
                    "rationale": "Valor de saturacion referido por debajo del rango esperado.",
                    "requires_human_review": True,
                }
            )
        elif checklist["disnea"] == "Presente" and not risk_flags:
            risk_mentions.append("Disnea referida durante esfuerzo; requiere correlacion clinica.")
            risk_flags.append(
                {
                    "severity": "low",
                    "category": "other",
                    "snippet": "Disnea asociada al esfuerzo",
                    "rationale": "Se describe sintoma respiratorio activo que amerita seguimiento.",
                    "requires_human_review": True,
                }
            )

        motivo = "Consulta por sintomas respiratorios y disminucion de tolerancia al esfuerzo."
        if "ronqu" in lowered or "apnea" in lowered:
            motivo = "Consulta por sintomas respiratorios y alteraciones del sueno con impacto funcional."

        summary = (
            "Sesion de terapia respiratoria orientada a caracterizar sintomas actuales, antecedentes relevantes, "
            "factores desencadenantes y plan de manejo no farmacologico para seguimiento profesional."
        )

        template_data = {
            "datos_personales_paciente": {
                "nombre_paciente": "No referido",
                "telefono": "No referido",
                "identificacion": "No referido",
                "fecha_nacimiento": "No referido",
                "direccion": "No referido",
                "profesion": "No referido",
                "email": "No referido",
            },
            "datos_identificacion": {
                "nombre_paciente": "No referido",
                "edad": "No referido",
                "sexo": "No referido",
                "fecha_consulta": "No referido",
                "motivo_consulta": motivo,
            },
            "enfermedad_actual_hpi": {
                "inicio_sintomas": hpi_inicio or "No referido",
                "evolucion": hpi_evolucion or "No referido",
                "sintomas_principales_respiratorios": ", ".join(symptoms_present) if symptoms_present else "No referido",
                "factores_desencadenantes": ", ".join(desencadenantes) if desencadenantes else "No referido",
                "tratamientos_previos": ", ".join(tratamientos_previos) if tratamientos_previos else "No referido",
                "estado_actual": "Refiere persistencia sintomatica con variacion segun esfuerzo y contexto.",
            },
            "antecedentes_relevantes": {
                "personales_respiratorios": antecedentes_respiratorios,
                "personales_cardiovasculares": antecedentes_cardiovasculares,
                "personales_quirurgicos": antecedentes_quirurgicos,
                "medicamentos_actuales": tratamientos_previos,
                "familiares_asma": ["No referido"] if "familia" not in lowered and "asma" not in lowered else ["Referido"],
                "familiares_alergias": ["No referido"] if "familia" not in lowered and "alerg" not in lowered else ["Referido"],
                "familiares_enfermedades_pulmonares": ["No referido"]
                if "familia" not in lowered and "pulmon" not in lowered
                else ["Referido"],
            },
            "sintomas_respiratorios_checklist": checklist,
            "evaluacion_clinica_respiratoria": {
                "patron_respiratorio_observado": "No referido",
                "tipo_respiracion": "No referido",
                "uso_musculos_accesorios": "No referido",
                "tolerancia_ejercicio": "Disminuida" if checklist["fatiga_ejercicio"] == "Presente" else "No referido",
                "calidad_respiracion": "Con variabilidad segun esfuerzo" if checklist["disnea"] == "Presente" else "No referido",
                "hallazgos_relevantes_mencionados_por_terapeuta": "No referido",
            },
            "pruebas_realizadas_en_consulta": pruebas,
            "impresion_clinica": (
                "Paciente con hallazgos compatibles con patron respiratorio disfuncional e intolerancia al esfuerzo; "
                "requiere revision profesional y seguimiento."
            ),
            "plan_terapeutico": [
                "Entrenamiento de respiracion diafragmatica guiada.",
                "Pausas respiratorias y control de ritmo ventilatorio en actividad.",
                "Seguimiento clinico en proxima sesion para revalorar sintomas y adherencia.",
            ],
        }

        payload = {
            "structured_output": {
                "metadata": {
                    "requires_human_review": True,
                    "confidence_overall": "medium",
                },
                "identificacion_minima": {
                    "nombre_paciente": None,
                    "edad_referida": None,
                    "ocupacion_referida": None,
                    "acompanantes_mencionados": [],
                },
                "motivo_consulta": motivo,
                "resumen_sesion": summary,
                "sintomas_o_malestares_referidos": symptoms_present or ["No referido"],
                "antecedentes_mencionados": [
                    "Antecedentes respiratorios referidos por paciente." if antecedentes_respiratorios else "No referido"
                ],
                "contexto_familiar_social_laboral": [
                    "Refiere impacto funcional en actividades de la vida diaria.",
                ],
                "factores_estresores_actuales": desencadenantes or ["No referido"],
                "factores_protectores": [
                    "Adherencia al proceso terapeutico.",
                    "Disposicion para seguimiento profesional.",
                ],
                "riesgos_mencionados": risk_mentions,
                "frases_textuales_clave": [
                    "Refiere sensacion de falta de aire durante esfuerzo.",
                ],
                "hipotesis_iniciales_para_revision": [
                    "Posible patron respiratorio disfuncional en contexto de desencadenantes ambientales y de esfuerzo.",
                ],
                "plan_o_proximos_pasos": template_data["plan_terapeutico"],
                "campos_inciertos_o_ambiguos": [
                    "No se documentan mediciones seriadas completas en la transcripcion.",
                ],
                "plantilla_historia_clinica_respiratoria": template_data,
            },
            "session_summary": summary,
            "clinical_profile_text": (
                "1) Datos de identificacion\n"
                "- Nombre del paciente: No referido\n"
                "- Edad: No referido\n"
                "- Sexo: No referido\n"
                "- Fecha consulta: No referido\n"
                f"- Motivo de consulta: {motivo}\n\n"
                "2) Enfermedad actual (HPI)\n"
                f"- Inicio de sintomas: {template_data['enfermedad_actual_hpi']['inicio_sintomas']}\n"
                f"- Evolucion: {template_data['enfermedad_actual_hpi']['evolucion']}\n"
                f"- Sintomas respiratorios principales: {template_data['enfermedad_actual_hpi']['sintomas_principales_respiratorios']}\n\n"
                "3) Antecedentes relevantes\n"
                "- Personales respiratorios/cardiovasculares/quirurgicos: revisar salida estructurada.\n\n"
                "4) Sintomas respiratorios actuales (Checklist)\n"
                "- Revisar salida estructurada para Presente/Ausente/No mencionado.\n\n"
                "5) Evaluacion clinica respiratoria\n"
                "- Requiere correlacion profesional segun hallazgos de consulta.\n\n"
                "6) Pruebas realizadas en consulta\n"
                f"- {', '.join(pruebas) if pruebas else 'No referido'}\n\n"
                "7) Impresion clinica\n"
                f"- {template_data['impresion_clinica']}\n\n"
                "8) Plan terapeutico\n"
                + "\n".join(f"- {item}" for item in template_data["plan_terapeutico"])
            ),
            "risk_flags": risk_flags,
        }

        return ClinicalGenerationResult.model_validate(payload)

    def _contains_any(self, text: str, terms: list[str]) -> bool:
        return any(term in text for term in terms)

    def _collect_items(self, text: str, terms: list[str]) -> list[str]:
        found = [term for term in terms if term in text]
        if not found:
            return []
        deduped: list[str] = []
        seen: set[str] = set()
        for item in found:
            if item not in seen:
                deduped.append(item)
                seen.add(item)
        return deduped

    def _status_for_terms(self, text: str, terms: list[str]) -> str:
        for term in terms:
            escaped = re.escape(term)
            if re.search(rf"\b(?:no|niega|sin)\s+(?:presenta\s+)?{escaped}\b", text):
                return "Ausente"
        for term in terms:
            if term in text:
                return "Presente"
        return "No mencionado"

    def _extract_phrase(self, text: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(0).strip(" .,;:")
                if value:
                    return value
        return None


def build_llm_adapter() -> BaseLLMAdapter:
    if settings.use_mock_openai or not settings.openai_api_key:
        return MockLLMAdapter()
    return OpenAIResponsesAdapter()
