import pytest
from pydantic import ValidationError

from app.domain.schemas import ClinicalGenerationResult


def test_clinical_schema_validation_success() -> None:
    payload = {
        "structured_output": {
            "metadata": {"requires_human_review": True, "confidence_overall": "medium"},
            "identificacion_minima": {
                "nombre_paciente": None,
                "edad_referida": None,
                "ocupacion_referida": None,
                "acompanantes_mencionados": [],
            },
            "motivo_consulta": "x",
            "resumen_sesion": "x",
            "sintomas_o_malestares_referidos": [],
            "antecedentes_mencionados": [],
            "contexto_familiar_social_laboral": [],
            "factores_estresores_actuales": [],
            "factores_protectores": [],
            "riesgos_mencionados": [],
            "frases_textuales_clave": [],
            "hipotesis_iniciales_para_revision": [],
            "plan_o_proximos_pasos": [],
            "campos_inciertos_o_ambiguos": [],
        },
        "session_summary": "Resumen",
        "clinical_profile_text": "Texto",
        "risk_flags": [],
    }

    model = ClinicalGenerationResult.model_validate(payload)
    assert model.structured_output.metadata.requires_human_review is True


def test_clinical_schema_validation_failure() -> None:
    with pytest.raises(ValidationError):
        ClinicalGenerationResult.model_validate({"structured_output": {}})