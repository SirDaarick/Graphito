/**
 * @file evidence.ts
 * @description Maps report indicators to the suspicious lines of the student code, so the code view
 * can explain a line when the teacher points at it. Only rows that name a real line are used.
 */
import type { IndicadorIntegridad } from "./api";

export interface LineEvidence {
    title: string;
    text: string;
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

/** Evidence grouped by 1-based line number, in the order received, without exact duplicates. No severity is kept. */
export function evidenceByLine(indicadores: IndicadorIntegridad[]): Map<number, LineEvidence[]> {
    const byLine = new Map<number, LineEvidence[]>();
    for (const ind of indicadores) {
        const line = ind.numero_linea;
        if (typeof line !== "number" || !Number.isInteger(line) || line < 1) continue;
        const entry: LineEvidence = { title: plainTitle(ind.tipo_alerta), text: plainText(ind.descripcion) };
        const list = byLine.get(line) ?? [];
        if (!list.some((e) => e.title === entry.title && e.text === entry.text)) list.push(entry);
        byLine.set(line, list);
    }
    return byLine;
}
