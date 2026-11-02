"""Short PDF report for the teacher (spec AR3): who, the result banner, the two scores that matter,
observations, comments and the code.

`PdfReportService.build_content` turns a report into a plain content model (verdict banner, metric
rows, notes, label); `generate_pdf` only lays it out. The content never
falls back to a conformity verdict for unknown or missing verdicts, prints NULL scores as not
evaluated, and has no discrepancy row (design D15). Text is kept ASCII for the standard fonts.
"""

import io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Any, Tuple
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    Preformatted,
)
from app.infrastructure.database.models import ReporteAnalisis
from app.presentation.schemas.analysis import ReporteAnalisisResponse

PDF_LABEL = "Apoyo a la decision docente, no un dictamen automatico. Los resultados pueden equivocarse."

# tone -> (background, border, text color). One neutral palette for every tone: the color
# never signals good or bad, the teacher decides what the metrics mean.
_NEUTRAL_TONE = ("#f8fafc", "#94a3b8", "#334155")
TONES = {
    tone: _NEUTRAL_TONE for tone in ("dual", "semantic", "stylometric", "clear", "neutral")
}

VERDICTS = {
    "DISCREPANCIA_DUAL": ("dual", "ALERTA DUAL: AMBOS ANALISIS SUPERARON SU UMBRAL"),
    "REVISION_SEMANTICA": ("semantic", "ALERTA: SIMILITUD CON LA REFERENCIA SOBRE EL UMBRAL"),
    "REVISION_ESTILOMETRICA": ("stylometric", "ALERTA: ESTILO COMPATIBLE CON CODIGO GENERADO SOBRE EL UMBRAL"),
    "SIN_ALERTAS": ("clear", "SIN ALERTAS: NINGUN ANALISIS SUPERO SU UMBRAL"),
    "NO_EVALUABLE": ("neutral", "NO EVALUABLE: AL MENOS UN ANALISIS NO PUDO HACERSE; SIN DICTAMEN AUTOMATICO"),
    "SIN_REFERENCIA": ("neutral", "SIN REFERENCIA: EL PROBLEMA NO TIENE CODIGO DE REFERENCIA"),
}

ENGINE_NOTES = {
    "stub": "Datos de prueba (stub): no es resultado de un modelo real.",
    "legacy": "Reporte anterior a la calibracion (legacy): no se recalcula.",
}


def verdict_banner(dictamen: Optional[str], estado: Optional[str]) -> Tuple[str, str]:
    """(tone, text) for the verdict; unknown or missing verdicts are never shown as conformity."""
    estado = estado or "COMPLETADO"
    if dictamen is None or estado != "COMPLETADO":
        return "neutral", f"SIN DICTAMEN: ANALISIS {estado}"
    if dictamen in VERDICTS:
        return VERDICTS[dictamen]
    return "neutral", f"NO EVALUABLE: DICTAMEN DESCONOCIDO ({dictamen})"


def _pct(value: Optional[float]) -> str:
    return f"{round(value * 100, 1)}%"


@dataclass(frozen=True)
class PdfContent:
    verdict_tone: str
    verdict_text: str
    # (analisis, resultado)
    metric_rows: List[Tuple[str, str]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    label: str = PDF_LABEL


class PdfReportService:
    """
    Servicio generador de reportes en PDF: solo lo esencial para el docente
    (quien, que se midio, el resultado y sus anotaciones).
    """

    @staticmethod
    def build_content(report: ReporteAnalisisResponse) -> PdfContent:
        """The content model handed to the renderer (spec AR3.2)."""
        dictamen = getattr(report.dictamen, "value", report.dictamen)
        estado = getattr(report.estado, "value", report.estado)
        tone, text = verdict_banner(dictamen, estado)

        # The headline similarity is the GraphCodeBERT one, as on screen; the lexical (Jaccard) score is not shown.
        if report.gcb_similarity is None:
            a_value = f"No evaluado ({report.gcb_estado or 'sin calcular'})"
        else:
            a_value = _pct(report.gcb_similarity)
        if report.estado_canal_b == "ABSTENIDO":
            b_value = "ABSTENIDO (codigo demasiado corto)"
        elif report.probabilidad_ia is None:
            b_value = f"No evaluado ({report.estado_canal_b or estado})"
        else:
            b_value = _pct(report.probabilidad_ia)
        metric_rows = [
            ("Similitud con la referencia", a_value),
            ("Estilo parecido a codigo generado por IA", b_value),
        ]
        notes = [ENGINE_NOTES[report.engine]] if report.engine in ENGINE_NOTES else []
        return PdfContent(tone, text, metric_rows, notes)
    @staticmethod
    def generate_pdf(
        report: ReporteAnalisis,
        student_author: Optional[str] = None,
        problem_title: Optional[str] = None,
        language: Optional[str] = None,
        student_code: Optional[str] = None,
        comments: Optional[List[Any]] = None,
    ) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=45,
            leftMargin=45,
            topMargin=45,
            bottomMargin=45,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=21,
            textColor=colors.HexColor("#0f172a"),
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#475569"),
        )
        h2_style = ParagraphStyle(
            "H2",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=12,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155"),
        )
        elements = []

        # 1. Header: the thesis (TT) title
        elements.append(Paragraph("GRAPHITO", subtitle_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(
            "Graphito: Sistema de comparación de código en C/C++ mediante similitud "
            "semántica para cursos introductorios de programación",
            title_style,
        ))
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3b82f6"), spaceAfter=14))
        # 2. Metadata Box
        date_str = report.fecha_analisis.strftime("%d/%m/%Y %H:%M") if report.fecha_analisis else datetime.utcnow().strftime("%d/%m/%Y %H:%M")
        meta_data = [
            [
                Paragraph("<b>Problema:</b>", body_style),
                Paragraph(escape(problem_title or "No especificado"), body_style),
                Paragraph("<b>Fecha:</b>", body_style),
                Paragraph(date_str, body_style),
            ],
            [
                Paragraph("<b>Estudiante:</b>", body_style),
                Paragraph(escape(student_author or "Anonimo / Desconocido"), body_style),
                Paragraph("<b>Lenguaje:</b>", body_style),
                Paragraph((language or "C/C++").upper(), body_style),
            ],
        ]

        meta_table = Table(meta_data, colWidths=[85, 195, 70, 170])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 16))

        content = PdfReportService.build_content(ReporteAnalisisResponse.model_validate(report))
        # 4. The two results that matter
        elements.append(Paragraph("Resultados", h2_style))
        metrics_data = [[Paragraph(f"<b>{h}</b>", body_style) for h in ("Analisis", "Resultado")]]
        for row in content.metric_rows:
            metrics_data.append([Paragraph(escape(cell), body_style) for cell in row])
        metrics_table = Table(metrics_data, colWidths=[280, 240])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(metrics_table)
        for note in content.notes:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(f"<i>{escape(note)}</i>", body_style))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(escape(content.label), body_style))
        elements.append(Spacer(1, 10))

        # 6. Observaciones y Anotaciones del Docente (si existen)
        if comments and len(comments) > 0:
            elements.append(Spacer(1, 14))
            elements.append(Paragraph("Anotaciones y Observaciones del Docente", h2_style))
            comment_table_data = [
                [
                    Paragraph("<b>Ubicacion</b>", body_style),
                    Paragraph("<b>Autor</b>", body_style),
                    Paragraph("<b>Fecha</b>", body_style),
                    Paragraph("<b>Observacion / Comentario</b>", body_style),
                ]
            ]
            for c in comments:
                line_val = getattr(c, "numero_linea", None)
                loc = f"Linea {line_val}" if line_val else "Nota General"
                autor = getattr(c, "autor_nombre", None) or (c.docente.nombre if getattr(c, "docente", None) else "Docente")
                c_date = c.created_at.strftime("%d/%m/%Y %H:%M") if hasattr(c, "created_at") and hasattr(c.created_at, "strftime") else "Reciente"
                comment_table_data.append([
                    Paragraph(f"<b>{loc}</b>", body_style),
                    Paragraph(autor, body_style),
                    Paragraph(c_date, body_style),
                    Paragraph(str(getattr(c, "contenido", "")).replace("\n", "<br/>"), body_style),
                ])
            comm_table = Table(comment_table_data, colWidths=[85, 105, 80, 250])
            comm_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f5f3ff")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#ddd6fe")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(comm_table)

        # 7. Codigo Fuente Evaluado (si esta disponible)
        if student_code:
            elements.append(Spacer(1, 16))
            elements.append(Paragraph(f"Codigo Fuente Evaluado ({student_author or 'Estudiante'})", h2_style))
            code_lines = student_code.splitlines()
            formatted_lines = []
            for i, line in enumerate(code_lines, 1):
                safe_line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                formatted_lines.append(f"{i:3d} | {safe_line}")
            code_text = "\n".join(formatted_lines)
            code_style = ParagraphStyle(
                "CodeBlock",
                parent=styles["Normal"],
                fontName="Courier",
                fontSize=7.5,
                leading=10,
                textColor=colors.HexColor("#0f172a"),
            )
            code_p = Preformatted(code_text, code_style)
            code_table = Table([[code_p]], colWidths=[520])
            code_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(code_table)

        elements.append(Spacer(1, 20))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94a3b8"), spaceAfter=10))

        # 8. Footer
        elements.append(Paragraph(
            "Generado por Graphito. Los resultados orientan la revision; no son una sancion automatica "
            "ni sustituyen el juicio del docente.",
            ParagraphStyle(
                "FooterNote",
                parent=styles["Normal"],
                fontName="Helvetica-Oblique",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#64748b"),
            ),
        ))
        doc.build(elements)
        buffer.seek(0)
        return buffer
