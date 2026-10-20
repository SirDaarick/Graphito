import { describe, expect, it } from "vitest";
import { channelAMethod, describeDictamen, engineLabel, gcbHeadline, plainVerdict, toComparison } from "./dictamen";
import type { ReporteAnalisis, ReportScoring } from "./api";

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

    it.each(PROTOTYPE_KEYS)("channelAMethod(%s) echoes the raw value", (key) => {
        expect(channelAMethod({ canal_a_metodo: key } as ReportScoring)).toBe(key);
    });

    it("maps known values", () => {
        expect(engineLabel("stub")).toBe("STUB (desarrollo, no es un modelo)");
        expect(engineLabel(null)).toBe("—");
        expect(channelAMethod({ canal_a_metodo: "jaccard" } as ReportScoring)).toBe("Jaccard léxico, 5 tokens");
    });
});

describe("gcbHeadline", () => {
    it("returns the GraphCodeBERT similarity as a whole percentage", () => {
        expect(gcbHeadline({ gcb_similarity: 0.974, gcb_estado: "OK" })).toEqual({ pct: 97, reason: null });
    });

    it("keeps a genuine zero as 0, never as unavailable", () => {
        expect(gcbHeadline({ gcb_similarity: 0, gcb_estado: "OK" })).toEqual({ pct: 0, reason: null });
    });

    it.each(["OK_SIN_NORM", "DEMO", null, undefined])("is available for state %s when a score exists", (estado) => {
        expect(gcbHeadline({ gcb_similarity: 0.5, gcb_estado: estado }).pct).toBe(50);
    });

    it("is unavailable, with a plain reason, when the score is null", () => {
        const result = gcbHeadline({ gcb_similarity: null, gcb_estado: null });
        expect(result.pct).toBeNull();
        expect(result.reason).toMatch(/reindex/i);
    });

    it.each([
        ["SIN_REFERENCIA", /referencia/i],
        ["SIN_INDICE", /indexad/i],
        ["DESHABILITADO", /desactivad/i],
        ["ERROR", /no se pudo/i],
    ])("explains the unavailable state %s", (estado, pattern) => {
        const result = gcbHeadline({ gcb_similarity: null, gcb_estado: estado });
        expect(result.pct).toBeNull();
        expect(result.reason).toMatch(pattern);
    });

    it("does not trust a score reported together with an unavailable state", () => {
        expect(gcbHeadline({ gcb_similarity: 0.9, gcb_estado: "ERROR" }).pct).toBeNull();
    });

    it.each(["constructor", "__proto__", "toString"])("falls back to the generic reason for state %s", (estado) => {
        const result = gcbHeadline({ gcb_similarity: null, gcb_estado: estado });
        expect(result.pct).toBeNull();
        expect(result.reason).toMatch(/reindex/i);
    });
});

describe("plainVerdict", () => {
    it.each([
        ["DISCREPANCIA_DUAL", true],
        ["REVISION_SEMANTICA", true],
        ["REVISION_ESTILOMETRICA", true],
        ["SIN_ALERTAS", false],
        ["NO_EVALUABLE", false],
        ["SIN_REFERENCIA", false],
    ])("gives %s one short sentence", (dictamen, flagged) => {
        const v = plainVerdict(dictamen, "COMPLETADO");
        expect(v.text.length).toBeGreaterThan(10);
        expect(v.flagged).toBe(flagged);
    });

    it("never turns an unknown verdict into a positive one", () => {
        const v = plainVerdict("SOSPECHA_IA", "COMPLETADO");
        expect(v.flagged).toBe(false);
        expect(v.text).toMatch(/no se pudo evaluar/i);
    });

    it("shows the analysis state while the report is not completed", () => {
        expect(plainVerdict("DISCREPANCIA_DUAL", "PROCESANDO").text).toMatch(/en proceso/i);
    });
});

describe("toComparison", () => {
    const base: ReporteAnalisis = { id: 7, entrega_id: "e", indicadores: [], estado: "COMPLETADO", dictamen: "SIN_ALERTAS" };

    it("lists the GraphCodeBERT similarity as the headline, not the literal Jaccard", () => {
        const view = toComparison({ ...base, similitud_semantica: 0.94, gcb_similarity: 0.62, gcb_estado: "OK" }, "Ana");
        expect(view.similarity).toBe(62);
    });

    it("lists no number (never 0) when GraphCodeBERT is not available", () => {
        const view = toComparison({ ...base, similitud_semantica: 0.94, gcb_similarity: null, gcb_estado: null }, "Ana");
        expect(view.similarity).toBeNull();
    });
});
