import { describe, expect, it } from "vitest";
import { calibrationLabel, channelAMethod, describeDictamen, engineLabel } from "./dictamen";
import type { ReportScoring } from "./api";

const KNOWN: Array<[string, string, string, boolean]> = [
    ["DISCREPANCIA_DUAL", "Similitud alta y estilo atípico", "dual", true],
    ["REVISION_SEMANTICA", "Similitud alta con la referencia", "semantic", true],
    ["REVISION_ESTILOMETRICA", "Estilo atípico", "stylometric", true],
    ["SIN_ALERTAS", "Similitud dentro de lo habitual", "clear", false],
    ["NO_EVALUABLE", "No evaluable", "neutral", false],
    ["SIN_REFERENCIA", "Sin referencia", "neutral", false],
];

const PROTOTYPE_KEYS = ["constructor", "toString", "__proto__", "hasOwnProperty", "valueOf"];

describe("describeDictamen", () => {
    it.each(KNOWN)("maps %s to its label and tone", (dictamen, label, tone, flagged) => {
        const info = describeDictamen(dictamen, "COMPLETADO");
        expect(info.label).toBe(label);
        expect(info.tone).toBe(tone);
        expect(info.flagged).toBe(flagged);
    });

    it.each(["SOSPECHA_IA", "PLAGIO_PROBABLE", "INTEGRO", "CONFORME", "algo_nuevo", ...PROTOTYPE_KEYS])(
        "maps unknown or legacy %s to No evaluable",
        (dictamen) => {
            const info = describeDictamen(dictamen, "COMPLETADO");
            expect(info.label).toBe("No evaluable");
            expect(info.tone).toBe("neutral");
            expect(info.flagged).toBe(false);
        },
    );

    it.each([null, undefined, ""])("treats a missing verdict (%s) on a completed report as Pendiente", (dictamen) => {
        const info = describeDictamen(dictamen, "COMPLETADO");
        expect(info.label).toBe("Pendiente");
        expect(info.tone).toBe("pending");
        expect(info.flagged).toBe(false);
    });

    it.each([
        ["PENDIENTE", "Pendiente"],
        ["PROCESANDO", "En proceso"],
        ["ERROR", "Error de análisis"],
    ])("shows the analysis state %s when the verdict is missing", (estado, label) => {
        expect(describeDictamen(null, estado).label).toBe(label);
        expect(describeDictamen("", estado).label).toBe(label);
    });

    it("gives a non-COMPLETADO state priority over a stored verdict", () => {
        const info = describeDictamen("DISCREPANCIA_DUAL", "PROCESANDO");
        expect(info.label).toBe("En proceso");
        expect(info.tone).toBe("pending");
        expect(info.flagged).toBe(false);
    });

    it.each(["DESCONOCIDO", ...PROTOTYPE_KEYS])("falls back to Pendiente for an unknown state %s", (estado) => {
        expect(describeDictamen("SIN_ALERTAS", estado).label).toBe("Pendiente");
    });

    it("treats a missing state as completed", () => {
        expect(describeDictamen("SIN_ALERTAS", null).label).toBe("Similitud dentro de lo habitual");
    });
});

describe("label lookups ignore prototype keys", () => {
    it.each(PROTOTYPE_KEYS)("engineLabel(%s) echoes the raw value", (key) => {
        expect(engineLabel(key)).toBe(key);
    });

    it.each(PROTOTYPE_KEYS)("calibrationLabel(%s) echoes the raw value", (key) => {
        expect(calibrationLabel(key)).toBe(key);
    });

    it.each(PROTOTYPE_KEYS)("channelAMethod(%s) echoes the raw value", (key) => {
        expect(channelAMethod({ canal_a_metodo: key } as ReportScoring)).toBe(key);
    });

    it("maps known values", () => {
        expect(engineLabel("stub")).toBe("STUB (desarrollo, no es un modelo)");
        expect(engineLabel(null)).toBe("—");
        expect(calibrationLabel("calibrado")).toBe("Calibrado (umbrales de artefactos)");
        expect(calibrationLabel(undefined)).toBe("Sin evaluar");
        expect(channelAMethod({ canal_a_metodo: "jaccard" } as ReportScoring)).toBe("Jaccard léxico, 5 tokens");
    });
});
