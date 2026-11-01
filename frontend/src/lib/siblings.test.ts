import { describe, expect, it } from "vitest";
import { siblingSubmissions } from "./siblings";
import type { CodigoFuente, Problema, ReporteAnalisis } from "./api";

function report(id: number): ReporteAnalisis {
    return { id, entrega_id: `e${id}`, indicadores: [], estado: "COMPLETADO", dictamen: "SIN_ALERTAS" };
}

function submission(autor: string, reportId?: number): CodigoFuente {
    return {
        id: `s-${autor}`,
        problema_id: 1,
        tipo: "ENTREGA_ALUMNO",
        autor,
        contenido: "",
        lenguaje: "c",
        created_at: "2026-01-01",
        reporte: reportId === undefined ? undefined : report(reportId),
    };
}

function problem(id: number, entregas: CodigoFuente[]): Problema {
    return { id, titulo: `P${id}`, enunciado: "", lenguaje: "c", fecha_creacion: "2026-01-01", entregas } as Problema;
}

describe("siblingSubmissions", () => {
    it("returns every analysed submission of the owning problem, titled by author", () => {
        const problems = [problem(1, [submission("Ana", 10), submission("Beto", 11), submission("Sin análisis")]), problem(2, [submission("Cris", 20)])];
        const result = siblingSubmissions(problems, 11)!;
        expect(result.list.map((c) => c.title)).toEqual(["Ana", "Beto"]);
        expect(result.current.title).toBe("Beto");
    });

    it("does not mix in submissions of other problems", () => {
        const problems = [problem(1, [submission("Ana", 10)]), problem(2, [submission("Cris", 20), submission("Dani", 21)])];
        expect(siblingSubmissions(problems, 20)!.list.map((c) => c.title)).toEqual(["Cris", "Dani"]);
    });

    it("returns null when no problem owns the report", () => {
        expect(siblingSubmissions([problem(1, [submission("Ana", 10)])], 99)).toBeNull();
        expect(siblingSubmissions([], 1)).toBeNull();
    });

    it("ignores problems loaded without submissions", () => {
        expect(siblingSubmissions([{ ...problem(1, []), entregas: undefined }], 10)).toBeNull();
    });
});
