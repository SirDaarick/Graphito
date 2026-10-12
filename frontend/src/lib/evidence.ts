/**
 * @file evidence.ts
 * @description Display rules for the XAI evidence drawer: per-channel text and indicator badges.
 *
 * Only rows the backend marks `origen: "decision"` come from the calibrated flags; every other row,
 * including one without `categoria`/`origen`, is a rule-based heuristic (spec AR4.1).
 */
import type { IndicadorIntegridad } from "./api";
import { lookupLabel } from "./dictamen";

export interface Badge {
    label: string;
    color: string;
}

/** Badges for rows driven by the calibrated decision flags. */
const DECISION_BADGES: Record<string, Badge> = {
    GENERAL: { label: "Decisión (bandera calibrada)", color: "text-rose-400" },
    SIMILITUD_ARCHIVO: { label: "Similitud léxica (archivo)", color: "text-purple-400" },
};

/** Badges for rule-based heuristic categories. */
const HEURISTIC_BADGES: Record<string, Badge> = {
    ESTILO_LLM: { label: "Heurística: patrón de documentación", color: "text-emerald-400" },
    NIVEL_AVANZADO: { label: "Heurística: construcción avanzada", color: "text-amber-400" },
    ISOMORFISMO_DFG: { label: "Heurística legada (DFG)", color: "text-slate-400" },
};

/** Neutral default for any row that is not an explicit decision row. */
export const HEURISTIC_BADGE: Badge = { label: "Heurística", color: "text-cyan-400" };

/** Channel states in which the channel produced a score (backend `PERSISTED_STATE`). */
const SCORED_STATES = new Set(["EVALUADO", "NO_CALIBRADO"]);

export function isHeuristic(ind: IndicadorIntegridad): boolean {
    return ind.origen !== "decision";
}

export function indicatorBadge(ind: IndicadorIntegridad): Badge {
    if (!isHeuristic(ind)) return lookupLabel(DECISION_BADGES, ind.categoria) ?? HEURISTIC_BADGE;
    return lookupLabel(HEURISTIC_BADGES, ind.categoria) ?? HEURISTIC_BADGE;
}

export interface ChannelTextInput {
    /** Displayed channel score; null or undefined when the channel produced none. */
    score: number | null | undefined;
    flag: boolean | null | undefined;
    estado: string | null | undefined;
    onFlag: string;
    onClear: string;
}

/**
 * Text for one channel pillar. A calibrated flag decides the text; a scored channel without a
 * flag is "sin calibrar" (its number is shown but does not decide); only a channel without a
 * score is "No evaluado".
 */
export function channelText({ score, flag, estado, onFlag, onClear }: ChannelTextInput): string {
    if (flag === true) return onFlag;
    if (flag === false) return onClear;
    const scored = (score !== null && score !== undefined) || (estado != null && SCORED_STATES.has(estado));
    if (scored) return "Evaluado sin calibrar: el puntaje se muestra, pero no hay bandera calibrada que decida.";
    return `No evaluado (${estado ?? "sin estado"}): este canal no aporta bandera.`;
}
