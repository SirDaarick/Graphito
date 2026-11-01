import { describe, expect, it } from "vitest";
import type { ExampleSummary } from "../api";
import { TOUR_FLOWS, getSteps, otherFlow } from "./steps";
import type { TourFlow } from "./types";

const FLOWS: TourFlow[] = ["own", "library", "examples"];
const SHARED_TAIL_FLOWS: TourFlow[] = ["own", "library"];

const EXAMPLES: ExampleSummary = {
    grupo_id: 7,
    creado: true,
    problemas: [{ problema_id: 31, titulo: "Ejemplo" }],
    recorrido: { problema_id: 31, casos: { identical: 101, similar: 102, different: 103, ai: 104 } },
};

describe("tour steps", () => {
    it.each(FLOWS)("%s: ids are unique", (flow) => {
        const ids = getSteps(flow).map((s) => s.id);
        expect(new Set(ids).size).toBe(ids.length);
    });

    it.each(FLOWS)("%s: only the last step is final and it has no target", (flow) => {
        const steps = getSteps(flow);
        expect(steps.filter((s) => s.final)).toHaveLength(1);
        const last = steps[steps.length - 1];
        expect(last.final).toBe(true);
        expect(last.target).toBeUndefined();
    });

    it.each(FLOWS)("%s: every other step has a target and short copy", (flow) => {
        for (const step of getSteps(flow).filter((s) => !s.final)) {
            expect(step.target, step.id).toBeTruthy();
            expect(step.text.length, step.id).toBeLessThanOrEqual(80);
        }
    });

    it.each(FLOWS)("%s: recoverTo points at an earlier step of the same flow", (flow) => {
        const steps = getSteps(flow);
        steps.forEach((step, index) => {
            if (!step.recoverTo) return;
            const target = steps.findIndex((s) => s.id === step.recoverTo);
            expect(target, `${step.id} -> ${step.recoverTo}`).toBeGreaterThanOrEqual(0);
            expect(target, `${step.id} -> ${step.recoverTo}`).toBeLessThan(index);
        });
    });

    it("own and library keep the exact step lists they had before the examples flow", () => {
        expect(getSteps("own").map((s) => s.id)).toEqual([
            "own-new-code",
            "own-title",
            "own-code",
            "own-submit",
            "cmp-open",
            "cmp-author",
            "cmp-code",
            "cmp-submit",
            "report-title",
            "report-verdict",
            "done",
        ]);
        expect(getSteps("library").map((s) => s.id)).toEqual([
            "lib-catalog",
            "lib-expand",
            "lib-program",
            "lib-add",
            "lib-go",
            "cmp-open",
            "cmp-author",
            "cmp-code",
            "cmp-submit",
            "report-title",
            "report-verdict",
            "done",
        ]);
    });

    it("own and library end with the same shared tail", () => {
        const tail = (flow: TourFlow) => getSteps(flow).filter((s) => s.id.startsWith("cmp-") || s.id.startsWith("report-") || s.final).map((s) => s.id);
        expect(tail("own")).toEqual(tail("library"));
        expect(tail("own")).toEqual(["cmp-open", "cmp-author", "cmp-code", "cmp-submit", "report-title", "report-verdict", "done"]);
    });

    it.each(SHARED_TAIL_FLOWS)("%s: no step needs the examples summary", (flow) => {
        for (const step of getSteps(flow)) {
            expect(step.enterRoute, step.id).toBeUndefined();
            expect(step.reportView, step.id).toBeUndefined();
        }
    });

    it("the chooser lists the three flows", () => {
        expect(TOUR_FLOWS.map((f) => f.flow)).toEqual(["own", "library", "examples"]);
        expect(TOUR_FLOWS.find((f) => f.flow === "examples")?.title).toBe("Ver ejemplos");
        expect(otherFlow("own")).toBe("library");
        expect(otherFlow("library")).toBe("own");
    });
});

describe("examples flow", () => {
    const steps = getSteps("examples");
    const byId = (id: string) => steps.find((s) => s.id === id)!;

    it("has its own ending and none of the shared tail", () => {
        expect(steps.some((s) => s.id.startsWith("cmp-") || s.id.startsWith("report-") || s.id === "done")).toBe(false);
        expect(steps[steps.length - 1].id).toBe("ex-done");
    });

    it("walks the cases in order: identical, similar, different, ai", () => {
        expect(steps.map((s) => s.id)).toEqual([
            "ex-library",
            "ex-identical-literal",
            "ex-identical-semantic",
            "ex-code-open",
            "ex-code-panes",
            "ex-similar-literal",
            "ex-similar-code",
            "ex-different-literal",
            "ex-different-code",
            "ex-ai-style",
            "ex-done",
        ]);
    });

    it.each([
        ["ex-similar-code", "/reporte/102", "ex-similar-literal"],
        ["ex-different-code", "/reporte/103", "ex-different-literal"],
    ])("%s shows the code panes of its own case", (id, route, recoverTo) => {
        expect(byId(id)).toMatchObject({ target: "code-panes", reportView: "code", advance: { kind: "manual" }, recoverTo });
        expect(byId(id).enterRoute?.({ problemId: 31, examples: EXAMPLES })).toBe(route);
    });

    it("opens the report of each case through enterRoute", () => {
        const route = (id: string) => byId(id).enterRoute?.({ problemId: 31, examples: EXAMPLES });
        expect(route("ex-library")).toBe("/biblioteca");
        expect(route("ex-identical-literal")).toBe("/reporte/101");
        expect(route("ex-code-open")).toBe("/reporte/101");
        expect(route("ex-code-panes")).toBe("/reporte/101");
        expect(route("ex-similar-literal")).toBe("/reporte/102");
        expect(route("ex-different-literal")).toBe("/reporte/103");
        expect(route("ex-ai-style")).toBe("/reporte/104");
        expect(route("ex-done")).toBe("/biblioteca");
    });

    it("has no report to open without the examples summary", () => {
        const route = (id: string) => byId(id).enterRoute?.({ problemId: null });
        expect(route("ex-identical-literal")).toBeNull();
        expect(route("ex-ai-style")).toBeNull();
    });

    it("explains Channel A on the literal card and Channel B on the style card", () => {
        expect(byId("ex-identical-literal").target).toBe("metric-literal");
        expect(byId("ex-similar-literal").target).toBe("metric-literal");
        expect(byId("ex-different-literal").target).toBe("metric-literal");
        expect(byId("ex-ai-style").target).toBe("metric-style");
        expect(byId("ex-identical-semantic").target).toBe("metric-semantic");
    });

    it("asks the user to open the code view, then shows the code panes", () => {
        expect(byId("ex-code-open")).toMatchObject({ target: "view-code", advance: { kind: "click" } });
        expect(byId("ex-code-panes")).toMatchObject({ target: "code-panes", reportView: "code" });
    });

    it("shows the summary of every report it opens", () => {
        for (const id of ["ex-identical-literal", "ex-code-open", "ex-similar-literal", "ex-different-literal", "ex-ai-style"]) {
            expect(byId(id).reportView, id).toBe("summary");
        }
    });

    it("selects the example group in the library on the first step", () => {
        expect(byId("ex-library")).toMatchObject({ target: "problem-card", scopedToProblem: true, showGroup: true });
        expect(steps.filter((s) => s.showGroup)).toHaveLength(1);
    });

    it("describes metrics without verdict words", () => {
        const verdict = /copia|sospech|plagi|fraude|cr[ií]tic|alerta|severidad|culpable|trampa/i;
        for (const step of steps) {
            expect(`${step.title} ${step.text}`, step.id).not.toMatch(verdict);
        }
    });

    it("closes by saying the teacher decides", () => {
        expect(byId("ex-done").text).toMatch(/docente/i);
    });
});
