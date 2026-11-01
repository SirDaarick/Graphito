/**
 * @file siblings.ts
 * @description Finds the other submissions of the problem a report belongs to, so a report opened
 * from a direct link (/reporte/:id) can still be paged like one opened from the library.
 */
import type { Problema } from "./api";
import { toComparison, type ComparisonView } from "./dictamen";

export interface ReportSiblings {
    current: ComparisonView;
    list: ComparisonView[];
}

/** Submissions of the problem that owns `reportId`, with their authors as titles; null when no problem has it. */
export function siblingSubmissions(problems: Problema[], reportId: number): ReportSiblings | null {
    for (const problem of problems) {
        const withReport = (problem.entregas ?? []).filter((s) => s.reporte);
        if (!withReport.some((s) => s.reporte!.id === reportId)) continue;
        const list = withReport.map((s) => toComparison(s.reporte!, s.autor, s.grupo_id));
        const current = list.find((c) => String(c.id) === String(reportId));
        return current ? { current, list } : null;
    }
    return null;
}
