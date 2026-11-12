/**
 * @file students.ts
 * @description Groups submissions by student. A student is only the free-text `autor` of a submission,
 * so names are compared in a normalized form (no case, accents or extra spaces).
 */
import type { Grupo, Problema } from "./api";
import { toComparison, type ComparisonView } from "./dictamen";

export function normalizeName(name: string): string {
    return name.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/\s+/g, " ").trim();
}

export interface StudentTask {
    problemId: number;
    problemTitle: string;
    groupName: string | null;
    lenguaje: string;
    date: string;
    /** Null while the submission has no analysis: there is no report to open. */
    comparison: ComparisonView | null;
}

export interface Student {
    key: string;
    name: string;
    tasks: StudentTask[];
}

export function groupStudents(problems: Problema[], groups: Grupo[]): Student[] {
    const byKey = new Map<string, Student>();
    for (const p of problems) {
        for (const s of p.entregas ?? []) {
            if (s.tipo !== "ENTREGA_ALUMNO") continue;
            const key = normalizeName(s.autor);
            if (!key) continue;
            const group = groups.find((g) => g.id === s.grupo_id);
            const comparison = s.reporte ? toComparison(s.reporte, s.autor, s.grupo_id) : null;
            if (comparison && group?.es_ejemplo) comparison.es_ejemplo = true;
            const student = byKey.get(key) ?? { key, name: s.autor.trim(), tasks: [] };
            student.tasks.push({
                problemId: p.id,
                problemTitle: p.titulo,
                groupName: group?.nombre ?? null,
                lenguaje: s.lenguaje,
                date: s.created_at,
                comparison,
            });
            byKey.set(key, student);
        }
    }
    const students = [...byKey.values()];
    students.forEach((st) => st.tasks.sort((a, b) => b.date.localeCompare(a.date)));
    return students.sort((a, b) => a.name.localeCompare(b.name, "es", { sensitivity: "base" }));
}

/** Every word of the query must appear in the name, in any order: "perez juan" finds "Juan Pérez". */
export function searchStudents(students: Student[], query: string): Student[] {
    const words = normalizeName(query).split(" ").filter(Boolean);
    return students.filter((st) => words.every((w) => st.key.includes(w)));
}
