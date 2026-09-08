import io
from datetime import datetime
from typing import Optional

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
)
from app.infrastructure.database.models import ReporteAnalisis, DictamenEnum


class PdfReportService:
    """
    Servicio generador de reportes academicos oficiales en formato PDF.
    Diseno formal para catedras universitarias y comisiones de integridad.
    """

    @staticmethod
    def generate_pdf(
        report: ReporteAnalisis,
        student_author: Optional[str] = None,
        problem_title: Optional[str] = None,
        language: Optional[str] = None,
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
                Paragraph(f"<b>{getattr(report, 'estado', 'COMPLETADO')}</b>", body_style),
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

        # 3. Verdict Banner
        dictamen_val = report.dictamen.value if hasattr(report.dictamen, "value") else str(report.dictamen)
        if dictamen_val == DictamenEnum.SOSPECHA_IA.value:
            verdict_bg = colors.HexColor("#fff7ed")
            verdict_border = colors.HexColor("#f97316")
            verdict_color = "#c2410c"
            verdict_text = "DICTAMEN: SOSPECHA DE GENERACION POR INTELIGENCIA ARTIFICIAL"
        elif dictamen_val == DictamenEnum.PLAGIO_PROBABLE.value:
            verdict_bg = colors.HexColor("#fef2f2")
            verdict_border = colors.HexColor("#ef4444")
            verdict_color = "#b91c1c"
            verdict_text = "DICTAMEN: ALTA PROBABILIDAD DE COPIA / PLAGIO"
        else:
            verdict_bg = colors.HexColor("#f0fdf4")
            verdict_border = colors.HexColor("#22c55e")
            verdict_color = "#15803d"
            verdict_text = "DICTAMEN: CODIGO INTEGRO (AUTORIA HUMANA ESPERADA)"

        verdict_paragraph = Paragraph(
            f"<font color='{verdict_color}'><b>{verdict_text}</b></font>",
            verdict_style,
        )
        verdict_table = Table([[verdict_paragraph]], colWidths=[520])
        verdict_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), verdict_bg),
            ('BOX', (0, 0), (-1, -1), 1.5, verdict_border),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(verdict_table)
        elements.append(Spacer(1, 16))

        # 4. Metrics Table
        elements.append(Paragraph("Desglose del Analisis Bimodal", h2_style))
        sem_pct = f"{round(report.similitud_semantica * 100, 1)}%"
        ai_pct = f"{round(report.probabilidad_ia * 100, 1)}%"
        disc_score = f"{round(report.discrepancia_score, 4)}"

        metrics_data = [
            [
                Paragraph("<b>Canal de Inspeccion</b>", body_style),
                Paragraph("<b>Tecnica Utilizada</b>", body_style),
                Paragraph("<b>Valor Obtenido</b>", body_style),
                Paragraph("<b>Interpretacion</b>", body_style),
            ],
            [
                Paragraph("<b>Canal A: Semantica</b>", body_style),
                Paragraph("Grafo de Flujo de Datos (Tree-Sitter DFG + GraphCodeBERT)", body_style),
                Paragraph(f"<b>{sem_pct}</b>", body_style),
                Paragraph("Similitud de logica interna independiente de identificadores", body_style),
            ],
            [
                Paragraph("<b>Canal B: Estilometria</b>", body_style),
                Paragraph("Clasificador Convolucional de Caracteres (CharCNN)", body_style),
                Paragraph(f"<b>{ai_pct}</b>", body_style),
                Paragraph("Probabilidad de patrones de sintaxis propios de LLMs", body_style),
            ],
            [
                Paragraph("<b>Discrepancia Asimetrica</b>", body_style),
                Paragraph("Calibracion Bimodal Ponderada", body_style),
                Paragraph(f"<b>{disc_score}</b>", body_style),
                Paragraph("Metrica de divergencia entre estructura y estilo", body_style),
            ],
        ]

        metrics_table = Table(metrics_data, colWidths=[120, 160, 90, 150])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(metrics_table)
        elements.append(Spacer(1, 16))

        # 5. Indicators Table
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
                indicators_data.append([
                    Paragraph(f"<b>{ind.tipo_alerta}</b>", body_style),
                    Paragraph(f"<font color='{sev_color}'><b>{sev}</b></font>", body_style),
                    Paragraph(ind.descripcion, body_style),
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
                "<i>No se registraron anomalias criticas ni patrones convergentes en el codigo analizado.</i>",
                body_style,
            ))

        elements.append(Spacer(1, 24))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#94a3b8"), spaceAfter=10))

        # 6. Legal / Institutional Footer
        elements.append(Paragraph(
            "<b>Nota de Certificacion:</b> Este reporte es generado de manera automatizada por la plataforma Graphito "
            "mediante analisis bimodal de grafos de flujo de datos y clasificadores estilometricos neuronales. "
            "El dictamen tecnico constituye una herramienta de asistencia al docente y no reemplaza la deliberacion "
            "academica de la catedra correspondiente.",
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
