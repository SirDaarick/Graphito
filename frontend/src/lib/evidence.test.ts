import { describe, expect, it } from "vitest";
import { HEURISTIC_BADGE, channelText, indicatorBadge, isHeuristic } from "./evidence";
import type { IndicadorIntegridad } from "./api";

const ON = "sobre el umbral";
const OFF = "bajo el umbral";

describe("channelText", () => {
    it("follows a raised or cleared calibrated flag", () => {
        expect(channelText({ score: 40, flag: true, estado: "EVALUADO", onFlag: ON, onClear: OFF })).toBe(ON);
        expect(channelText({ score: 10, flag: false, estado: "EVALUADO", onFlag: ON, onClear: OFF })).toBe(OFF);
    });

    it("explains a scored channel without a flag as uncalibrated, never as not evaluated", () => {
        const text = channelText({ score: 37, flag: null, estado: "NO_CALIBRADO", onFlag: ON, onClear: OFF });
        expect(text).toMatch(/sin calibrar/i);
        expect(text).not.toMatch(/no evaluado/i);
    });

    it("treats a legacy score with no flag and no state as uncalibrated", () => {
        const text = channelText({ score: 0, flag: undefined, estado: undefined, onFlag: ON, onClear: OFF });
        expect(text).toMatch(/sin calibrar/i);
    });

    it("treats an evaluated state without score or flag as uncalibrated", () => {
        expect(channelText({ score: null, flag: null, estado: "NO_CALIBRADO", onFlag: ON, onClear: OFF })).toMatch(
            /sin calibrar/i,
        );
    });

    it("reports a channel without a score as not evaluated, with its state", () => {
        const text = channelText({ score: null, flag: null, estado: "SIN_REFERENCIA", onFlag: ON, onClear: OFF });
        expect(text).toMatch(/no evaluado/i);
        expect(text).toContain("SIN_REFERENCIA");
        expect(channelText({ score: null, flag: null, estado: null, onFlag: ON, onClear: OFF })).toContain("sin estado");
    });
});

function ind(extra: Partial<IndicadorIntegridad>): IndicadorIntegridad {
    return { tipo_alerta: "X", descripcion: "d", severidad: "MEDIA", ...extra };
}

describe("indicatorBadge", () => {
    it("gives the decision badge only to rows with origen decision", () => {
        expect(indicatorBadge(ind({ categoria: "GENERAL", origen: "decision" })).label).toBe("Decisión (bandera calibrada)");
        expect(indicatorBadge(ind({ categoria: "SIMILITUD_ARCHIVO", origen: "decision" })).label).toBe(
            "Similitud léxica (archivo)",
        );
    });

    it("defaults rows without categoria or origen to the neutral heuristic badge", () => {
        expect(indicatorBadge(ind({}))).toEqual(HEURISTIC_BADGE);
        expect(indicatorBadge(ind({ categoria: "GENERAL" }))).toEqual(HEURISTIC_BADGE);
        expect(indicatorBadge(ind({ categoria: "GENERAL", origen: "heuristica" }))).toEqual(HEURISTIC_BADGE);
    });

    it("labels known heuristic categories", () => {
        expect(indicatorBadge(ind({ categoria: "ESTILO_LLM", origen: "heuristica" })).label).toBe(
            "Heurística: patrón de documentación",
        );
    });

    it.each(["constructor", "toString", "__proto__"])("falls back for prototype key %s", (key) => {
        expect(indicatorBadge(ind({ categoria: key }))).toEqual(HEURISTIC_BADGE);
        expect(indicatorBadge(ind({ categoria: key, origen: "decision" }))).toEqual(HEURISTIC_BADGE);
    });
});

describe("isHeuristic", () => {
    it("is false only for decision rows", () => {
        expect(isHeuristic(ind({ origen: "decision" }))).toBe(false);
        expect(isHeuristic(ind({ origen: "heuristica" }))).toBe(true);
        expect(isHeuristic(ind({}))).toBe(true);
        expect(isHeuristic(ind({ categoria: "GENERAL" }))).toBe(true);
    });
});
