/**
 * @file dictamen.ts
 * @description Single mapping from the backend verdict (dictamen) and analysis state to UI copy.
 *
 * Every verdict is mapped explicitly. A missing verdict is "Pendiente" (or the analysis state),
 * and an unknown or legacy value is "No evaluable": no branch ever turns into a positive
 * verdict (spec AR2.1, AR2.2). The teacher's own decision (decision_docente) is separate.
 */
import type { IndicadorIntegridad, ReporteAnalisis, ReportScoring } from "./api";

/** A report as listed and opened in the UI: the report fields plus display text. */
export interface ComparisonView extends ReportScoring {
    id: string | number;
    title: string;
    subtitle: string;
    /** Headline semantic similarity (GraphCodeBERT) as a whole percentage; null when not available. */
    similarity: number | null;
    indicadores?: IndicadorIntegridad[];
    grupo_id?: number;
    /** The teacher's mark as saved on the server (persists across sessions and devices). */
    decision_docente?: ReporteAnalisis["decision_docente"];
}

export function toComparison(report: ReporteAnalisis, title: string, grupoId?: number): ComparisonView {
    return {
        ...report,
        id: String(report.id),
        title,
        subtitle: `Resumen de similitud: ${describeDictamen(report.dictamen, report.estado).label}`,
        similarity: gcbHeadline(report).pct,
        grupo_id: grupoId,
    };
}

/**
 * Own-property lookup for label maps keyed by backend strings: inherited keys such as
 * "constructor", "toString" or "__proto__" are unknown values, never a label.
 */
export function lookupLabel<T>(map: Readonly<Record<string, T>>, key: string | null | undefined): T | undefined {
    return key != null && Object.hasOwn(map, key) ? map[key] : undefined;
}

export type VerdictTone = "dual" | "semantic" | "stylometric" | "clear" | "neutral" | "pending";

export interface VerdictInfo {
    label: string;
    /** Descriptive grouping only; it carries no color and no severity. */
    tone: VerdictTone;
}

const VERDICTS: Record<string, VerdictInfo> = {
    DISCREPANCIA_DUAL: { label: "Similitud alta y estilo atípico", tone: "dual" },
    REVISION_SEMANTICA: { label: "Similitud alta con la referencia", tone: "semantic" },
    REVISION_ESTILOMETRICA: { label: "Estilo atípico", tone: "stylometric" },
    SIN_ALERTAS: { label: "Similitud dentro de lo habitual", tone: "clear" },
    NO_EVALUABLE: { label: "No evaluable", tone: "neutral" },
    SIN_REFERENCIA: { label: "Sin referencia", tone: "neutral" },
};

const NOT_EVALUABLE: VerdictInfo = { label: "No evaluable", tone: "neutral" };

const PENDING_STATES: Record<string, string> = {
    PENDIENTE: "Pendiente",
    PROCESANDO: "En proceso",
    ERROR: "Error de análisis",
};

export function describeDictamen(dictamen?: string | null, estado?: string | null): VerdictInfo {
    if (estado && estado !== "COMPLETADO") {
        return { label: lookupLabel(PENDING_STATES, estado) ?? "Pendiente", tone: "pending" };
    }
    if (dictamen === null || dictamen === undefined || dictamen === "") {
        return { label: "Pendiente", tone: "pending" };
    }
    return lookupLabel(VERDICTS, dictamen) ?? NOT_EVALUABLE;
}

/** Score in [0, 1] as a whole percentage, or null when not evaluated (never 0). */
export function toPct(value?: number | null): number | null {
    return value === null || value === undefined ? null : Math.round(value * 100);
}

/** Display text for an optional percentage: a dash when not evaluated. */
export function formatPct(value?: number | null): string {
    const pct = toPct(value);
    return pct === null ? "—" : `${pct}%`;
}

export function formatNumber(value?: number | null, digits = 4): string {
    return value === null || value === undefined ? "—" : value.toFixed(digits);
}

export function formatFlag(flag?: boolean | null): string {
    return flag === null || flag === undefined ? "—" : flag ? "Sí" : "No";
}

export const CHANNEL_A_METHODS: Record<string, string> = {
    jaccard: "Jaccard léxico, 5 tokens",
};

export function channelAMethod(report: ReportScoring): string {
    if (report.canal_a_metodo) return lookupLabel(CHANNEL_A_METHODS, report.canal_a_metodo) ?? report.canal_a_metodo;
    return report.engine === "legacy" ? "Legado (GraphCodeBERT sin calibrar)" : "—";
}

export const GCB_LABEL = "Normalización de identificadores · exploratorio, no decide";

/** Spec AR1.4: shown with every report; the backend sends the full text in etiqueta_validacion. */
export const VALIDATION_LABEL = "No validado contra plagio derivado de la referencia";

export const ENGINE_LABELS: Record<string, string> = {
    real: "Motor real",
    stub: "STUB (desarrollo, no es un modelo)",
    legacy: "Reporte legado (sin calibración)",
    demo: "DEMO (datos de ejemplo)",
};

export const CALIBRATION_LABELS: Record<string, string> = {
    calibrado: "Calibrado (umbrales de artefactos)",
    no_calibrado: "No calibrado: sin banderas",
    stub: "Umbrales fijos de desarrollo",
    legacy: "Sin calibración (legado)",
    demo: "Datos de ejemplo (DEMO, sin calibración)",
};

export function calibrationLabel(state?: string | null): string {
    return state ? lookupLabel(CALIBRATION_LABELS, state) ?? state : "Sin evaluar";
}

export function engineLabel(engine?: string | null): string {
    return engine ? lookupLabel(ENGINE_LABELS, engine) ?? engine : "—";
}

/** Channel B is abstained when the code is too short for CharCNN. */
export function isAbstained(report: ReportScoring): boolean {
    return report.estado_canal_b === "ABSTENIDO";
}

export interface GcbHeadline {
    /** Whole percentage, or null when the measurement is not available (never 0 in that case). */
    pct: number | null;
    /** One plain sentence explaining why there is no number; null when there is one. */
    reason: string | null;
}

const GCB_UNAVAILABLE: Record<string, string> = {
    SIN_REFERENCIA: "Este problema todavía no tiene soluciones de referencia con las que comparar.",
    SIN_INDICE: "Las referencias aún no están indexadas para esta medición.",
    DESHABILITADO: "Esta medición está desactivada en este equipo.",
    ERROR: "No se pudo calcular esta medición.",
};

const GCB_PENDING_REASON = "Aún no se calculó para esta entrega. Hay que reindexar las referencias y volver a analizar.";

/** The headline semantic similarity (GraphCodeBERT). Unavailable is explicit, never a 0 %. */
export function gcbHeadline(report: Pick<ReportScoring, "gcb_similarity" | "gcb_estado">): GcbHeadline {
    const stateReason = lookupLabel(GCB_UNAVAILABLE, report.gcb_estado);
    if (stateReason) return { pct: null, reason: stateReason };
    const pct = toPct(report.gcb_similarity);
    return pct === null ? { pct: null, reason: GCB_PENDING_REASON } : { pct, reason: null };
}
