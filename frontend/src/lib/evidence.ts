/**
 * @file evidence.ts
 * @description Maps report indicators to the suspicious lines of the student code, so the code view
 * can explain a line when the teacher points at it. Only rows that name a real line are used.
 */
import type { IndicadorIntegridad } from "./api";
import { lookupLabel } from "./dictamen";

export interface LineEvidence {
    title: string;
    text: string;
    severity: string;
}

const SEVERITY_RANK: Record<string, number> = { BAJA: 0, MEDIA: 1, ALTA: 2, CRITICA: 3 };

function rank(severity: string): number {
    return lookupLabel(SEVERITY_RANK, severity.toUpperCase()) ?? -1;
}

function capitalize(text: string): string {
    return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Removes technical wording that adds nothing for a teacher ("Heurística", "Línea N:"). */
function plainTitle(title: string): string {
    return title.replace(/^Heur[ií]stica:\s*/i, "").trim();
}

function plainText(text: string): string {
    const cleaned = text
        .replace(/^Heur[ií]stica \(no es salida del modelo\)\.\s*/i, "")
        .replace(/^L[ií]nea \d+:\s*/i, "")
        .trim();
    return capitalize(cleaned);
}

/** Evidence grouped by 1-based line number, most severe first, without exact duplicates. */
export function evidenceByLine(indicadores: IndicadorIntegridad[]): Map<number, LineEvidence[]> {
    const byLine = new Map<number, LineEvidence[]>();
    for (const ind of indicadores) {
        const line = ind.numero_linea;
        if (typeof line !== "number" || !Number.isInteger(line) || line < 1) continue;
        const entry: LineEvidence = { title: plainTitle(ind.tipo_alerta), text: plainText(ind.descripcion), severity: ind.severidad };
        const list = byLine.get(line) ?? [];
        if (!list.some((e) => e.title === entry.title && e.text === entry.text)) list.push(entry);
        byLine.set(line, list);
    }
    for (const list of byLine.values()) list.sort((a, b) => rank(b.severity) - rank(a.severity));
    return byLine;
}
