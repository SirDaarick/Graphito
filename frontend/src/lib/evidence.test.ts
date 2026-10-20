import { describe, expect, it } from "vitest";
import { evidenceByLine } from "./evidence";
import type { IndicadorIntegridad } from "./api";

function ind(extra: Partial<IndicadorIntegridad>): IndicadorIntegridad {
    return { tipo_alerta: "X", descripcion: "d", severidad: "MEDIA", ...extra };
}

describe("evidenceByLine", () => {
    it("keeps only indicators that point at a real line", () => {
        const map = evidenceByLine([
            ind({ numero_linea: 7, descripcion: "uno" }),
            ind({ numero_linea: null }),
            ind({ numero_linea: undefined }),
            ind({ numero_linea: 0 }),
            ind({ numero_linea: -3 }),
            ind({ numero_linea: 2.5 }),
        ]);
        expect([...map.keys()]).toEqual([7]);
    });

    it("groups several indicators on the same line, most severe first", () => {
        const map = evidenceByLine([
            ind({ numero_linea: 4, severidad: "BAJA", tipo_alerta: "Baja", descripcion: "a" }),
            ind({ numero_linea: 4, severidad: "CRITICA", tipo_alerta: "Crítica", descripcion: "b" }),
            ind({ numero_linea: 4, severidad: "MEDIA", tipo_alerta: "Media", descripcion: "c" }),
        ]);
        expect(map.get(4)?.map((e) => e.title)).toEqual(["Crítica", "Media", "Baja"]);
    });

    it("drops exact duplicates on a line", () => {
        const dup = ind({ numero_linea: 3, tipo_alerta: "T", descripcion: "mismo texto" });
        expect(evidenceByLine([dup, { ...dup }]).get(3)).toHaveLength(1);
    });

    it("strips the technical heuristic wording and the line prefix from the text", () => {
        const [entry] = evidenceByLine([
            ind({
                numero_linea: 178,
                tipo_alerta: "Heurística: Patrón de Documentación LLM",
                descripcion: "Heurística (no es salida del modelo). Línea 178: comentarios paso a paso frecuentes en código generado.",
            }),
        ]).get(178)!;
        expect(entry.title).toBe("Patrón de Documentación LLM");
        expect(entry.text).toBe("Comentarios paso a paso frecuentes en código generado.");
    });

    it("treats an unknown severity as the lowest one without throwing", () => {
        const map = evidenceByLine([
            ind({ numero_linea: 1, severidad: "constructor", tipo_alerta: "raro" }),
            ind({ numero_linea: 1, severidad: "ALTA", tipo_alerta: "alta" }),
        ]);
        expect(map.get(1)?.map((e) => e.title)).toEqual(["alta", "raro"]);
    });

    it("returns an empty map for no indicators", () => {
        expect(evidenceByLine([]).size).toBe(0);
    });
});
