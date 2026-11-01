import { describe, expect, it } from "vitest";
import {
    INITIAL_TOUR_STATE,
    currentStep,
    resolveTargetSelectors,
    routeAdvancesStep,
    stepProgress,
    tourReducer,
} from "./machine";
import { getSteps } from "./steps";
import type { TourAction } from "./machine";
import type { TourState } from "./types";

function run(actions: TourAction[], from: TourState = INITIAL_TOUR_STATE): TourState {
    return actions.reduce(tourReducer, from);
}

describe("tourReducer", () => {
    it("opens the chooser from idle", () => {
        expect(run([{ type: "open" }]).status).toBe("choosing");
    });

    it("starts the chosen flow at its first step", () => {
        const state = run([{ type: "open" }, { type: "choose", flow: "library" }]);
        expect(state).toMatchObject({ status: "running", flow: "library", stepIndex: 0 });
        expect(currentStep(state)?.id).toBe("lib-catalog");
    });

    it("ignores choose while idle", () => {
        expect(run([{ type: "choose", flow: "own" }])).toEqual(INITIAL_TOUR_STATE);
    });

    it("moves forward and back, never below the first step", () => {
        const started = run([{ type: "open" }, { type: "choose", flow: "own" }]);
        expect(run([{ type: "back" }], started).stepIndex).toBe(0);
        expect(run([{ type: "next" }, { type: "next" }, { type: "back" }], started).stepIndex).toBe(1);
    });

    it("finishes after the last step", () => {
        const steps = getSteps("own");
        const started = run([{ type: "open" }, { type: "choose", flow: "own" }]);
        const atLast = run(Array(steps.length - 1).fill({ type: "next" }), started);
        expect(currentStep(atLast)?.final).toBe(true);
        expect(run([{ type: "next" }], atLast)).toEqual(INITIAL_TOUR_STATE);
    });

    it("jumps to a step by id and ignores unknown ids", () => {
        const started = run([{ type: "open" }, { type: "choose", flow: "own" }]);
        const jumped = run([{ type: "goTo", stepId: "cmp-author" }], started);
        expect(currentStep(jumped)?.id).toBe("cmp-author");
        expect(run([{ type: "goTo", stepId: "nope" }], started)).toBe(started);
    });

    it("exit resets everything", () => {
        const started = run([{ type: "open" }, { type: "choose", flow: "own" }, { type: "next" }]);
        expect(run([{ type: "exit" }], started)).toEqual(INITIAL_TOUR_STATE);
    });

    it("keeps the problem id only while running and clears it on a new flow", () => {
        expect(run([{ type: "setProblem", problemId: 7 }]).context.problemId).toBeNull();
        const started = run([{ type: "open" }, { type: "choose", flow: "own" }, { type: "setProblem", problemId: 7 }]);
        expect(started.context.problemId).toBe(7);
        expect(run([{ type: "choose", flow: "library" }], started).context.problemId).toBeNull();
    });

    it("reports progress over the whole flow", () => {
        const started = run([{ type: "open" }, { type: "choose", flow: "library" }, { type: "next" }]);
        expect(stepProgress(started)).toEqual({ current: 2, total: getSteps("library").length });
        expect(stepProgress(INITIAL_TOUR_STATE)).toEqual({ current: 0, total: 0 });
    });
});

describe("resolveTargetSelectors", () => {
    const compare = getSteps("own").find((s) => s.id === "cmp-open")!;
    const title = getSteps("own").find((s) => s.id === "own-title")!;
    const done = getSteps("own").find((s) => s.final)!;

    it("prefers the element of the tour's problem, then any", () => {
        expect(resolveTargetSelectors(compare, { problemId: 12 })).toEqual([
            '[data-tour="compare"][data-problem-id="12"]',
            '[data-tour="compare"]',
        ]);
        expect(resolveTargetSelectors(compare, { problemId: null })).toEqual(['[data-tour="compare"]']);
    });

    it("ignores the problem id on unscoped steps", () => {
        expect(resolveTargetSelectors(title, { problemId: 12 })).toEqual(['[data-tour="ref-title"]']);
    });

    it("returns nothing for a centered card", () => {
        expect(resolveTargetSelectors(done, { problemId: null })).toEqual([]);
    });
});

describe("routeAdvancesStep", () => {
    const toCatalog = getSteps("library")[0];
    const toReport = getSteps("own").find((s) => s.id === "cmp-submit")!;
    const clickStep = getSteps("own")[0];

    it("matches literal and parametrized routes", () => {
        expect(routeAdvancesStep(toCatalog, "/catalogo")).toBe(true);
        expect(routeAdvancesStep(toCatalog, "/biblioteca")).toBe(false);
        expect(routeAdvancesStep(toReport, "/reporte/42")).toBe(true);
        expect(routeAdvancesStep(toReport, "/reporte")).toBe(false);
    });

    it("never advances click steps by route", () => {
        expect(routeAdvancesStep(clickStep, "/catalogo")).toBe(false);
    });
});
