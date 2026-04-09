"""Template renderers for Respiro Integral clinical formats."""

from __future__ import annotations

import re
import textwrap
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

try:
    from pypdf import PdfReader, PdfWriter
except Exception:  # pragma: no cover
    PdfReader = None
    PdfWriter = None


@dataclass(slots=True)
class _Rect:
    x: float
    y: float
    width: float
    height: float


class RespiroTemplateRenderer:
    """Render helper for Respira Integral DOCX/PDF templates."""

    _W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    _TOP_FIELDS = {
        "patient_name": _Rect(33, 637, 170, 31),
        "identification": _Rect(215, 637, 132, 31),
        "date": _Rect(355, 637, 111, 31),
        "age": _Rect(474, 637, 120, 31),
        "birth_date": _Rect(33, 576, 162, 31),
        "phone": _Rect(206, 576, 140, 31),
        "city": _Rect(355, 576, 238, 31),
        "email": _Rect(33, 510, 302, 31),
    }

    _PAGE1_BOXES = {
        "motivo": _Rect(33, 375, 530, 110),
        "antecedentes": _Rect(33, 242, 530, 112),
        "perfil": _Rect(33, 54, 530, 165),
    }

    _PAGE2_BOXES = {
        "evaluacion": _Rect(33, 562, 258, 112),
        "auscultacion": _Rect(304, 562, 258, 112),
        "oxigenoterapia": _Rect(33, 435, 258, 101),
        "escalas": _Rect(304, 435, 258, 101),
        "plan": _Rect(33, 290, 530, 118),
        "recomendaciones": _Rect(33, 163, 530, 109),
    }

    _PROFESSIONAL_BOX = _Rect(33, 69, 258, 80)
    _RESPONSABLE_BOX = _Rect(304, 69, 258, 80)

    def is_respiro_template(self, path: Path | str) -> bool:
        candidate = Path(path)
        name = candidate.name.lower()
        if any(
            token in name
            for token in (
                "historia_clinica_respira_integral",
                "historia_clinica_respira",
                "respira_integral",
            )
        ):
            return True

        if candidate.suffix.lower() == ".docx" and candidate.exists():
            try:
                with ZipFile(candidate, "r") as source_zip:
                    xml = source_zip.read("word/document.xml").decode("utf-8", errors="ignore").lower()
                return all(
                    marker in xml
                    for marker in (
                        "historia cl",
                        "nombre / firma / fecha",
                        "registro profesional",
                    )
                )
            except Exception:
                return False
        return False

    def render_docx(self, *, template_path: str, output_path: str, fields: dict[str, Any]) -> bool:
        template = Path(template_path)
        if not template.exists():
            return False

        slots = self._build_slots(fields)

        with ZipFile(template, "r") as source_zip:
            document_xml = source_zip.read("word/document.xml")
            root = ET.fromstring(document_xml)

            paragraphs = root.findall(".//w:p", {"w": self._W_NS})
            normalized_groups = self._group_paragraphs(paragraphs)

            self._replace_exact_groups(normalized_groups, "nombre completo", slots["patient_name"])
            self._replace_exact_groups(normalized_groups, "cc / ti / pasaporte", slots["identification"])
            self._replace_exact_groups(normalized_groups, "+57", slots["phone"])
            self._replace_exact_groups(normalized_groups, "ciudad / municipio", slots["city"])
            self._replace_exact_groups(normalized_groups, "correo@ejemplo.com", slots["email"])

            self._replace_sequence(
                normalized_groups.get("dd/mm/aaaa", []),
                [slots["date"], slots["date"], slots["birth_date"], slots["birth_date"]],
            )

            self._replace_exact_groups(
                normalized_groups,
                "sintomas principales, tiempo de evolucion y objetivo de la valoracion.",
                slots["motivo"],
            )
            self._replace_exact_groups(
                normalized_groups,
                "diagnostico medico, antecedentes respiratorios, alergias, medicacion actual y comorbilidades.",
                slots["antecedentes"],
            )
            self._replace_exact_groups(
                normalized_groups,
                "observacion general del estado del paciente, funcionalidad y hallazgos de la primera valoracion.",
                slots["perfil"],
            )
            self._replace_exact_groups(
                normalized_groups,
                "patron ventilatorio, uso de musculos accesorios, frecuencia y tolerancia al esfuerzo.",
                slots["evaluacion"],
            )
            self._replace_exact_groups(
                normalized_groups,
                "ruidos respiratorios, localizacion, tipo de secrecion y manejo de via aerea.",
                slots["auscultacion"],
            )
            self._replace_exact_groups(
                normalized_groups,
                "dispositivo, flujo, respuesta clinica y observaciones.",
                slots["oxigenoterapia"],
            )
            self._replace_exact_groups(
                normalized_groups,
                "disnea, dolor, saturacion basal y pruebas funcionales.",
                slots["escalas"],
            )
            self._replace_exact_groups(
                normalized_groups,
                "objetivos, tecnicas propuestas, frecuencia sugerida y metas clinicas.",
                slots["plan"],
            )
            self._replace_exact_groups(
                normalized_groups,
                "educacion, ejercicios, signos de alarma y cuidados en casa.",
                slots["recomendaciones"],
            )

            signatures = normalized_groups.get("nombre / firma / fecha", [])
            self._replace_sequence(
                signatures,
                [
                    slots["professional_signature"],
                    slots["professional_signature"],
                    slots["responsable_signature"],
                    slots["responsable_signature"],
                ],
            )
            self._replace_sequence(
                normalized_groups.get("registro profesional", []),
                [slots["professional_registry"], slots["professional_registry"]],
            )

            rendered_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)

            with ZipFile(output, "w") as target_zip:
                for item in source_zip.infolist():
                    if item.filename == "word/document.xml":
                        target_zip.writestr(item, rendered_xml)
                    else:
                        target_zip.writestr(item, source_zip.read(item.filename))

        return True

    def render_pdf(
        self,
        *,
        template_path: str,
        output_path: str,
        fields: dict[str, Any],
        signature_image_path: str | None,
        therapist_name: str | None,
    ) -> bool:
        if PdfReader is None or PdfWriter is None:
            return False

        template = Path(template_path)
        if not template.exists():
            return False

        reader = PdfReader(str(template))
        if not reader.pages:
            return False

        slots = self._build_slots(fields)
        if therapist_name and therapist_name.strip():
            slots["professional_name"] = therapist_name.strip()
            slots["professional_signature"] = f"{slots['professional_name']} / Firma / {slots['date']}"

        writer = PdfWriter()
        for page_index, page in enumerate(reader.pages):
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)

            overlay_buffer = BytesIO()
            overlay = canvas.Canvas(overlay_buffer, pagesize=(width, height))
            overlay.setFillColor(colors.HexColor("#111827"))

            if page_index == 0:
                self._draw_page_one(overlay, slots)
            if page_index == 1:
                self._draw_page_two(overlay, slots, signature_image_path)

            overlay.save()
            overlay_buffer.seek(0)
            overlay_page = PdfReader(overlay_buffer).pages[0]
            page.merge_page(overlay_page)
            writer.add_page(page)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as fh:
            writer.write(fh)

        return True

    def _draw_page_one(self, overlay: canvas.Canvas, slots: dict[str, str]) -> None:
        for key, rect in self._TOP_FIELDS.items():
            self._draw_single_line(
                overlay,
                rect,
                slots.get(key, "No referido"),
                font_size=9,
                y_offset=10,
                clear_background=False,
            )

        self._draw_text_box(overlay, self._PAGE1_BOXES["motivo"], slots["motivo"], reserve_top=58)
        self._draw_text_box(overlay, self._PAGE1_BOXES["antecedentes"], slots["antecedentes"], reserve_top=58)
        self._draw_text_box(overlay, self._PAGE1_BOXES["perfil"], slots["perfil"], reserve_top=58)

    def _draw_page_two(
        self,
        overlay: canvas.Canvas,
        slots: dict[str, str],
        signature_image_path: str | None,
    ) -> None:
        self._draw_text_box(overlay, self._PAGE2_BOXES["evaluacion"], slots["evaluacion"], reserve_top=52)
        self._draw_text_box(overlay, self._PAGE2_BOXES["auscultacion"], slots["auscultacion"], reserve_top=52)
        self._draw_text_box(overlay, self._PAGE2_BOXES["oxigenoterapia"], slots["oxigenoterapia"], reserve_top=52)
        self._draw_text_box(overlay, self._PAGE2_BOXES["escalas"], slots["escalas"], reserve_top=52)
        self._draw_text_box(overlay, self._PAGE2_BOXES["plan"], slots["plan"], reserve_top=52)
        self._draw_text_box(overlay, self._PAGE2_BOXES["recomendaciones"], slots["recomendaciones"], reserve_top=52)

        # Keep both signature fields text-free; only place therapist signature image centered.
        signature_path = Path(signature_image_path) if signature_image_path else None
        if signature_path and signature_path.exists():
            self._draw_centered_signature_image(
                overlay=overlay,
                signature_path=signature_path,
                box=self._PROFESSIONAL_BOX,
            )

    def _draw_single_line(
        self,
        overlay: canvas.Canvas,
        rect: _Rect,
        text: str,
        *,
        font_size: float,
        y_offset: float = 8,
        clear_background: bool = False,
    ) -> None:
        if clear_background:
            overlay.saveState()
            overlay.setFillColor(colors.white)
            overlay.rect(rect.x + 6, rect.y + 6, rect.width - 12, rect.height - 12, stroke=0, fill=1)
            overlay.restoreState()

        overlay.setFillColor(colors.HexColor("#111827"))
        value = self._safe_value(text)
        char_width = max(int((rect.width - 10) / (font_size * 0.56)), 12)
        line = textwrap.shorten(value, width=char_width, placeholder="...")
        overlay.setFont("Helvetica", font_size)
        overlay.drawString(rect.x + 6, rect.y + y_offset, line)

    def _draw_text_box(
        self,
        overlay: canvas.Canvas,
        rect: _Rect,
        text: str,
        *,
        reserve_top: float,
    ) -> None:
        overlay.setFont("Helvetica", 8.2)
        content = self._safe_value(text)
        wrap_width = max(int((rect.width - 12) / 4.35), 22)
        lines = textwrap.wrap(content, width=wrap_width)

        current_y = rect.y + rect.height - reserve_top
        min_y = rect.y + 10
        for line in lines:
            if current_y <= min_y:
                break
            overlay.drawString(rect.x + 6, current_y, line)
            current_y -= 9.2

    def _draw_centered_signature_image(
        self,
        *,
        overlay: canvas.Canvas,
        signature_path: Path,
        box: _Rect,
    ) -> None:
        try:
            image = ImageReader(str(signature_path))
            width_raw, height_raw = image.getSize()
            if width_raw <= 0 or height_raw <= 0:
                return

            max_width = max(box.width - 6, 20)
            max_height = max(box.height - 6, 20)
            scale = min(max_width / width_raw, max_height / height_raw)

            draw_width = width_raw * scale
            draw_height = height_raw * scale
            draw_x = box.x + (box.width - draw_width) / 2
            draw_y = box.y + (box.height - draw_height) / 2

            overlay.drawImage(
                image,
                draw_x,
                draw_y,
                width=draw_width,
                height=draw_height,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            return

    def _build_slots(self, fields: dict[str, Any]) -> dict[str, str]:
        sections_raw = fields.get("sections", [])
        sections = sections_raw if isinstance(sections_raw, list) else []

        sections_map: dict[str, list[str]] = {}
        for item in sections:
            if not isinstance(item, dict):
                continue
            title = self._normalize(item.get("title", ""))
            body = str(item.get("body", ""))
            lines = [line.strip() for line in body.splitlines() if line.strip()]
            sections_map[title] = lines

        identificacion = self._section_for(sections_map, ["datos de identificacion"])
        hpi = self._section_for(sections_map, ["enfermedad actual"])
        antecedentes = self._section_for(sections_map, ["antecedentes relevantes"])
        evaluacion = self._section_for(sections_map, ["evaluacion clinica respiratoria"])
        pruebas = self._section_for(sections_map, ["pruebas realizadas en consulta"])
        impresion = self._section_for(sections_map, ["impresion clinica"])
        plan = self._section_for(sections_map, ["plan terapeutico"])
        riesgos = self._section_for(sections_map, ["riesgos y alertas"])

        patient_name = self._safe_value(fields.get("patient_name"))
        age = self._safe_value(fields.get("age"))
        date = self._safe_value(fields.get("date"))
        birth_date = self._safe_value(fields.get("birth_date"))
        phone = self._safe_value(fields.get("phone"))
        city = self._safe_value(fields.get("city"))
        email = self._safe_value(fields.get("email"))
        identification = self._safe_value(fields.get("identification"))

        motivo = self._extract_labeled(identificacion, "motivo de consulta")
        if not motivo:
            motivo = self._compact(hpi, max_chars=180)

        antecedentes_text = self._compact(antecedentes, max_chars=170)
        perfil_text = self._compact(impresion or hpi, max_chars=170)
        evaluacion_text = self._compact(evaluacion, max_chars=150)

        auscultacion_text = self._search_line(
            evaluacion + antecedentes,
            ["hallazgos", "auscult", "secre", "ruidos"],
        )
        if not auscultacion_text:
            auscultacion_text = self._compact(evaluacion, max_chars=150)

        oxigeno_text = self._search_line(
            pruebas + plan,
            ["oxigen", "o2", "satur", "flujo", "dispositivo"],
        )

        escalas_text = self._compact(pruebas, max_chars=140)
        plan_text = self._compact(plan, max_chars=170)
        recomendaciones_text = self._compact(plan + riesgos, max_chars=170)

        professional_name = self._safe_value(fields.get("therapist_name") or "Profesional tratante")
        professional_signature = f"{professional_name} / Firma / {date}"
        responsable_signature = f"{patient_name} / Firma / {date}"

        return {
            "patient_name": patient_name,
            "identification": identification,
            "date": date,
            "age": age,
            "birth_date": birth_date,
            "phone": phone,
            "city": city,
            "email": email,
            "motivo": self._safe_value(motivo),
            "antecedentes": self._safe_value(antecedentes_text),
            "perfil": self._safe_value(perfil_text),
            "evaluacion": self._safe_value(evaluacion_text),
            "auscultacion": self._safe_value(auscultacion_text),
            "oxigenoterapia": self._safe_value(oxigeno_text),
            "escalas": self._safe_value(escalas_text),
            "plan": self._safe_value(plan_text),
            "recomendaciones": self._safe_value(recomendaciones_text),
            "professional_name": professional_name,
            "professional_signature": professional_signature,
            "responsable_signature": responsable_signature,
            "professional_registry": "Registro profesional: No referido",
        }

    def _section_for(self, sections: dict[str, list[str]], hints: list[str]) -> list[str]:
        for key, lines in sections.items():
            if any(hint in key for hint in hints):
                return lines
        return []

    def _extract_labeled(self, lines: list[str], label: str) -> str:
        wanted = self._normalize(label)
        for line in lines:
            normalized = self._normalize(line)
            if not normalized.startswith(wanted):
                continue
            if ":" in line:
                return line.split(":", 1)[1].strip()
            return line.strip("- ").strip()
        return ""

    def _search_line(self, lines: list[str], hints: list[str]) -> str:
        for line in lines:
            normalized = self._normalize(line)
            if any(hint in normalized for hint in hints):
                return self._strip_line(line)
        return ""

    def _compact(self, lines: list[str], *, max_chars: int) -> str:
        cleaned: list[str] = []
        for line in lines:
            value = self._strip_line(line)
            if not value:
                continue
            if self._normalize(value) in {"personales", "familiares"}:
                continue
            cleaned.append(value)

        if not cleaned:
            return "No referido"

        joined = "; ".join(cleaned)
        if len(joined) <= max_chars:
            return joined
        return textwrap.shorten(joined, width=max_chars, placeholder="...")

    def _strip_line(self, line: str) -> str:
        value = line.strip().lstrip("- ").strip()
        return value

    def _safe_value(self, value: Any) -> str:
        if value is None:
            return "No referido"
        text = str(value).strip()
        return text if text else "No referido"

    def _group_paragraphs(self, paragraphs: list[ET.Element]) -> dict[str, list[ET.Element]]:
        groups: dict[str, list[ET.Element]] = {}
        for paragraph in paragraphs:
            text = self._paragraph_text(paragraph)
            normalized = self._normalize(text)
            if not normalized:
                continue
            groups.setdefault(normalized, []).append(paragraph)
        return groups

    def _replace_exact_groups(self, groups: dict[str, list[ET.Element]], normalized_key: str, value: str) -> None:
        targets = groups.get(normalized_key, [])
        for paragraph in targets:
            self._set_paragraph_text(paragraph, value)

    def _replace_sequence(self, paragraphs: list[ET.Element], values: list[str]) -> None:
        for index, paragraph in enumerate(paragraphs):
            replacement = values[index] if index < len(values) else values[-1]
            self._set_paragraph_text(paragraph, replacement)

    def _paragraph_text(self, paragraph: ET.Element) -> str:
        texts = []
        for node in paragraph.findall(".//w:t", {"w": self._W_NS}):
            if node.text:
                texts.append(node.text)
        return "".join(texts).strip()

    def _set_paragraph_text(self, paragraph: ET.Element, value: str) -> None:
        safe = self._safe_value(value)
        text_nodes = paragraph.findall(".//w:t", {"w": self._W_NS})
        if not text_nodes:
            run = ET.SubElement(paragraph, f"{{{self._W_NS}}}r")
            text_node = ET.SubElement(run, f"{{{self._W_NS}}}t")
            text_node.text = safe
            return

        text_nodes[0].text = safe
        for node in text_nodes[1:]:
            node.text = ""

    def _normalize(self, value: Any) -> str:
        text = str(value or "").lower()
        normalized = unicodedata.normalize("NFKD", text)
        clean = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        clean = clean.replace("\n", " ")
        return re.sub(r"\s+", " ", clean).strip()










