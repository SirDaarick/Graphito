import { describe, expect, it } from "vitest";
import { groupStudents, normalizeName, searchStudents } from "./students";
import type { CodigoFuente, Grupo, Problema } from "./api";

function sub(autor: string, created_at: string, extra: Partial<CodigoFuente> = {}): CodigoFuente {
    return { id: `${autor}-${created_at}`, problema_id: 1, tipo: "ENTREGA_ALUMNO", autor, contenido: "", lenguaje: "c", created_at, ...extra };
}

function problem(id: number, entregas: CodigoFuente[]): Problema {
    return { id, titulo: `P${id}`, enunciado: "", lenguaje: "c", fecha_creacion: "2026-01-01", entregas } as Problema;
}

const groups = [{ id: 7, nombre: "2CM1" } as Grupo];

describe("normalizeName", () => {
    it("ignores case, accents and extra spaces", () => {
        expect(normalizeName("  JUAN   Pérez ")).toBe("juan perez");
    });
});

describe("groupStudents", () => {
    const students = groupStudents(
        [
            problem(1, [sub("Juan Pérez", "2026-01-01", { grupo_id: 7 }), sub("ana", "2026-01-02")]),
            problem(2, [sub("juan perez", "2026-02-01"), sub("Ref", "2026-02-02", { tipo: "REFERENCIA" })]),
        ],
        groups
    );

    it("joins spellings of one name, newest task first, and skips references", () => {
        expect(students.map((s) => s.key)).toEqual(["ana", "juan perez"]);
        expect(students[1].tasks.map((t) => t.problemId)).toEqual([2, 1]);
    });

    it("names the group and leaves unanalysed tasks without a report", () => {
        expect(students[1].tasks[1].groupName).toBe("2CM1");
        expect(students[1].tasks[0].comparison).toBeNull();
    });
});

describe("searchStudents", () => {
    const students = groupStudents([problem(1, [sub("Juan Pérez", "2026-01-01"), sub("Ana Gómez", "2026-01-01")])], []);

    it("matches in any order, case and accent", () => {
        expect(searchStudents(students, "PEREZ juan").map((s) => s.name)).toEqual(["Juan Pérez"]);
    });

    it("returns everyone for an empty query", () => {
        expect(searchStudents(students, "  ")).toHaveLength(2);
    });
});
