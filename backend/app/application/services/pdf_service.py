"""Institutional PDF report (spec AR3).

`PdfReportService.build_content` turns a report into a plain content model (verdict banner, metric
rows, provenance rows, validation label); `generate_pdf` only lays it out. The content never
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

PDF_LABEL = (
    "No validado contra plagio derivado de la referencia: umbrales calibrados con pares "
    "estudiante-estudiante. Apoyo a la decision docente, no un dictamen automatico."
)

# tone -> (background, border, text color)
TONES = {
    "dual": ("#faf5ff", "#8b5cf6", "#6d28d9"),
    "semantic": ("#fef2f2", "#ef4444", "#b91c1c"),
    "stylometric": ("#fff7ed", "#f97316", "#c2410c"),
    "clear": ("#f0fdf4", "#22c55e", "#15803d"),
    "neutral": ("#f8fafc", "#94a3b8", "#475569"),
}

VERDICTS = {
    "DISCREPANCIA_DUAL": ("dual", "ALERTA DUAL: AMBOS CANALES SUPERARON SU UMBRAL CALIBRADO"),
    "REVISION_SEMANTICA": ("semantic", "ALERTA CANAL A: SIMILITUD LEXICA CON LA REFERENCIA SOBRE EL UMBRAL"),
    "REVISION_ESTILOMETRICA": ("stylometric", "ALERTA CANAL B: ESTILO COMPATIBLE CON CODIGO GENERADO SOBRE EL UMBRAL"),
    "SIN_ALERTAS": ("clear", "SIN ALERTAS: NINGUN CANAL SUPERO SU UMBRAL CALIBRADO"),
    "NO_EVALUABLE": ("neutral", "NO EVALUABLE: AL MENOS UN CANAL NO PUDO EVALUARSE; SIN DICTAMEN AUTOMATICO"),
    "SIN_REFERENCIA": ("neutral", "SIN REFERENCIA: EL PROBLEMA NO TIENE CODIGO DE REFERENCIA (CANAL A NO EVALUADO)"),
}

METHODS_A = {"jaccard": "Jaccard lexico, shingles de 5 tokens"}
ENGINES = {
    "real": "real (artefactos de despliegue verificados)",
    "stub": "stub (desarrollo; no es resultado de un modelo)",
    "legacy": "legacy (reporte anterior a la calibracion; no se recalcula)",
}
CALIBRATION_STATES = {
    "calibrado": "calibrado (umbrales de los artefactos)",
    "no_calibrado": "NO calibrado (solo desarrollo): banderas nulas",
    "stub": "stub: umbrales fijos de desarrollo",
    "legacy": "legacy: sin calibracion",
}


def verdict_banner(dictamen: Optional[str], estado: Optional[str]) -> Tuple[str, str]:
    """(tone, text) for the verdict; unknown or missing verdicts are never shown as conformity."""
    estado = estado or "COMPLETADO"
    if dictamen is None or estado != "COMPLETADO":
        return "neutral", f"SIN DICTAMEN: ANALISIS {estado}"
    if dictamen in VERDICTS:
        return VERDICTS[dictamen]
    return "neutral", f"NO EVALUABLE: DICTAMEN DESCONOCIDO ({dictamen})"


def _num(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:.4f}"


def _pct(value: Optional[float]) -> str:
    return f"{round(value * 100, 1)}%"


def _flag(value: Optional[bool]) -> str:
    return "-" if value is None else ("SI" if value else "NO")


def _sha(value: Optional[str]) -> str:
    return value[:12] if value else "-"


def _threshold(umbral: Optional[float], clave: Optional[str], estado: Optional[str], flag: Optional[bool]) -> str:
    key = f" ({clave})" if clave else ""
    return f"umbral {_num(umbral)}{key}; estado {estado or '-'}; bandera {_flag(flag)}"


@dataclass(frozen=True)
class PdfContent:
    verdict_tone: str
    verdict_text: str
    # (canal, metodo, valor, umbral/estado)
    metric_rows: List[Tuple[str, str, str, str]] = field(default_factory=list)
    provenance_rows: List[Tuple[str, str]] = field(default_factory=list)
    label: str = PDF_LABEL


class PdfReportService:
    """
    Servicio generador de reportes academicos oficiales en formato PDF.
    Diseno formal para catedras universitarias y comisiones de integridad.
    """

    @staticmethod
    def build_content(report: ReporteAnalisisResponse) -> PdfContent:
        """The content model handed to the renderer (spec AR3.2)."""
        dictamen = getattr(report.dictamen, "value", report.dictamen)
        estado = getattr(report.estado, "value", report.estado)
        tone, text = verdict_banner(dictamen, estado)

        if report.similitud_semantica is None:
            a_value = f"No evaluado ({report.estado_canal_a or estado})"
        else:
            a_value = f"Jaccard {_pct(report.similitud_semantica)}"
            if report.puntaje_calibrado_a is not None:
                a_value += f"; calibrado {_num(report.puntaje_calibrado_a)}"
        if report.estado_canal_b == "ABSTENIDO":
            b_value = "ABSTENIDO (codigo demasiado corto para CharCNN)"
        elif report.probabilidad_ia is None:
            b_value = f"No evaluado ({report.estado_canal_b or estado})"
        else:
            b_value = f"calibrado {_num(report.probabilidad_ia)}"
        gcb_value = (
            f"coseno {_num(report.gcb_similarity)}" if report.gcb_similarity is not None
            else f"No disponible ({report.gcb_estado or '-'})"
        )
        legacy = report.engine == "legacy"
        method_a = METHODS_A.get(report.canal_a_metodo or "", report.canal_a_metodo or (
            "Legado: GraphCodeBERT sin calibrar" if legacy else "-"
        ))
        metric_rows = [
            ("Canal A: similitud con la referencia", method_a, a_value,
             _threshold(report.umbral_a, report.clave_umbral_a, report.estado_canal_a, report.flag_a)),
            ("Canal B: estilometria", "Legado: CharCNN sin calibrar" if legacy else "CharCNN v2 (caracteres)", b_value,
             _threshold(report.umbral_b, report.clave_umbral_b, report.estado_canal_b, report.flag_b)),
            ("Senal secundaria", "GraphCodeBERT con normalizacion de identificadores (exploratorio, no decide)", gcb_value, "no interviene en el dictamen"),
        ]
        versions = report.versiones_modelo or {}
        version_text = ", ".join(f"{k}={v}" for k, v in versions.items() if v is not None) or "-"
        provenance_rows = [
            ("Motor", ENGINES.get(report.engine or "", report.engine or "-")),
            ("Estado de calibracion", CALIBRATION_STATES.get(report.estado_calibracion or "", "sin evaluar")),
            ("Manifiesto de despliegue (sha256)", _sha(report.manifest_sha)),
            ("Calibracion A / B (sha256)", f"{_sha(report.calibracion_sha_a)} / {_sha(report.calibracion_sha_b)}"),
            ("Checkpoint CharCNN (sha256)", _sha(report.checkpoint_sha_b)),
            ("Versiones de modelo", version_text),
        ]
        return PdfContent(tone, text, metric_rows, provenance_rows)

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
            fontSize=22,
            leading=26,
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
        verdict_style = ParagraphStyle(
            "Verdict",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            alignment=1,
        )

        elements = []

        # 1. Header
        elements.append(Paragraph("GRAPHITO | Sistema Bimodal de Integridad Academica", subtitle_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph("Reporte Oficial de Evaluacion de Codigo", title_style))
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3b82f6"), spaceAfter=14))

        # 2. Metadata Box
        date_str = report.fecha_analisis.strftime("%d/%m/%Y %H:%M:%S UTC") if report.fecha_analisis else datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")
        meta_data = [
            [
                Paragraph("<b>ID Reporte:</b>", body_style),
                Paragraph(f"REP_{report.id}", body_style),
                Paragraph("<b>Fecha y Hora:</b>", body_style),
                Paragraph(date_str, body_style),
            ],
            [
                Paragraph("<b>Problema / Ejercicio:</b>", body_style),
                Paragraph(problem_title or "No especificado", body_style),
                Paragraph("<b>Lenguaje:</b>", body_style),
                Paragraph((language or "C/C++").upper(), body_style),
            ],
            [
                Paragraph("<b>Estudiante Evaluado:</b>", body_style),
                Paragraph(student_author or "Anonimo / Desconocido", body_style),
                Paragraph("<b>Estado:</b>", body_style),
                Paragraph(f"<b>{getattr(report.estado, 'value', report.estado) or 'COMPLETADO'}</b>", body_style),
            ],
        ]

        meta_table = Table(meta_data, colWidths=[120, 140, 110, 150])
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

        # 3. Decision Support Diagnostic Banner (never a conformity fallback, spec AR3.1)
        content = PdfReportService.build_content(ReporteAnalisisResponse.model_validate(report))
        verdict_bg, verdict_border, verdict_color = TONES[content.verdict_tone]
        verdict_paragraph = Paragraph(
            f"<font color='{verdict_color}'><b>{escape(content.verdict_text)}</b></font>",
            verdict_style,
        )
        verdict_table = Table([[verdict_paragraph]], colWidths=[520])
        verdict_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(verdict_bg)),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor(verdict_border)),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(verdict_table)
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(f"<b>{escape(content.label)}</b>", body_style))
        elements.append(Spacer(1, 12))

        # 4. Metrics Table: method, value (or not evaluated), threshold + key, state and flag.
        elements.append(Paragraph("Desglose del Analisis Bimodal", h2_style))
        header = ["Canal", "Metodo", "Valor", "Umbral y estado"]
        metrics_data = [[Paragraph(f"<b>{h}</b>", body_style) for h in header]]
        for row in content.metric_rows:
            metrics_data.append([Paragraph(escape(cell), body_style) for cell in row])
        metrics_table = Table(metrics_data, colWidths=[115, 135, 120, 150])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(metrics_table)
        elements.append(Spacer(1, 10))

        provenance_data = [
            [Paragraph(f"<b>{escape(k)}</b>", body_style), Paragraph(escape(v), body_style)]
            for k, v in content.provenance_rows
        ]
        provenance_table = Table(provenance_data, colWidths=[180, 340])
        provenance_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(provenance_table)
        elements.append(Spacer(1, 16))

        # 5. Indicators Table (rule-based rows are marked as heuristics, spec AR4.1)
        elements.append(Paragraph("Indicadores y Evidencias de Integridad", h2_style))
        if report.indicadores and len(report.indicadores) > 0:
            indicators_data = [
                [
                    Paragraph("<b>Alerta / Categoria</b>", body_style),
                    Paragraph("<b>Severidad</b>", body_style),
                    Paragraph("<b>Detalle Observado</b>", body_style),
                ]
            ]
            for ind in report.indicadores:
                sev = getattr(ind, 'severidad', 'MEDIA')
                sev_color = "#ef4444" if sev in ("ALTA", "CRITICA") else "#f59e0b" if sev == "MEDIA" else "#10b981"
                categoria = getattr(ind, "categoria", None) or "GENERAL"
                origin = "decision" if categoria in ("GENERAL", "SIMILITUD_ARCHIVO") else "heuristica"
                indicators_data.append([
                    Paragraph(f"<b>{escape(ind.tipo_alerta)}</b><br/>({origin})", body_style),
                    Paragraph(f"<font color='{sev_color}'><b>{escape(sev)}</b></font>", body_style),
                    Paragraph(escape(ind.descripcion), body_style),
                ])
            ind_table = Table(indicators_data, colWidths=[130, 80, 310])
            ind_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(ind_table)
        else:
            elements.append(Paragraph(
                "<i>Sin indicadores registrados para este reporte.</i>",
                body_style,
            ))

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

        # 8. Legal / Institutional Footer
        elements.append(Paragraph(
            "<b>Aviso Institucional (Sistema de Soporte a la Decision):</b> Este reporte es generado por la plataforma Graphito "
            "con dos canales calibrados (Canal A: similitud lexica Jaccard con la referencia; Canal B: estilometria CharCNN v2); "
            "GraphCodeBERT solo aporta una senal exploratoria que no decide. Las indicaciones heuristicas no son salida de un modelo. "
            "Los resultados orientan la revision; no constituyen una sancion disciplinaria automatica ni sustituyen el juicio "
            "academico y pedagogico del docente evaluador.",
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
