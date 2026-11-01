import { describe, expect, it } from "vitest";
import { shouldSkipStep, type TourEnv } from "./skip";
import { getSteps } from "./steps";
import type { TourStep } from "./types";

const env = (over: Partial<TourEnv> = {}): TourEnv => ({
    path: "/biblioteca",
    hasTarget: () => false,
    filledOnArrival: false,
    ...over,
});

const step = (id: string): TourStep => {
    const found = [...getSteps("own"), ...getSteps("library")].find((s) => s.id === id);
    if (!found) throw new Error(`unknown step ${id}`);
    return found;
};

describe("shouldSkipStep", () => {
    it("never skips a step without conditions", () => {
        expect(shouldSkipStep(step("report-title"), { problemId: 1 }, env())).toBe(false);
    });

    it("skips 'new code' when its modal is already open", () => {
        const open = env({ hasTarget: (name) => name === "ref-title" });
        expect(shouldSkipStep(step("own-new-code"), { problemId: null }, open)).toBe(true);
        expect(shouldSkipStep(step("own-new-code"), { problemId: null }, env())).toBe(false);
    });

    it("skips the exercise steps once the teacher already has a problem", () => {
        for (const id of ["own-title", "own-code", "own-submit"]) {
            expect(shouldSkipStep(step(id), { problemId: 5 }, env())).toBe(true);
            expect(shouldSkipStep(step(id), { problemId: null }, env())).toBe(false);
        }
    });

    it("skips a field step only when it was already filled on arrival", () => {
        expect(shouldSkipStep(step("cmp-author"), { problemId: 5 }, env({ filledOnArrival: true }))).toBe(true);
        expect(shouldSkipStep(step("cmp-author"), { problemId: 5 }, env())).toBe(false);
    });

    it("skips the catalog steps already satisfied by the current route or an open program", () => {
        expect(shouldSkipStep(step("lib-catalog"), { problemId: null }, env({ path: "/catalogo" }))).toBe(true);
        expect(shouldSkipStep(step("lib-catalog"), { problemId: null }, env())).toBe(false);
        const open = env({ hasTarget: (name) => name === "catalog-add" });
        expect(shouldSkipStep(step("lib-program"), { problemId: null }, open)).toBe(true);
    });

    it("skips the comparison steps when the report is already open", () => {
        const report = env({ path: "/reporte/12" });
        for (const id of ["cmp-open", "cmp-author", "cmp-code", "cmp-submit"]) {
            expect(shouldSkipStep(step(id), { problemId: 5 }, report)).toBe(true);
        }
    });
});
