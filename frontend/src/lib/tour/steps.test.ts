import { describe, expect, it } from "vitest";
import { TOUR_FLOWS, getSteps, otherFlow } from "./steps";
import type { TourFlow } from "./types";

const FLOWS: TourFlow[] = ["own", "library"];

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

    it("both flows end with the same shared tail", () => {
        const tail = (flow: TourFlow) => getSteps(flow).filter((s) => s.id.startsWith("cmp-") || s.id.startsWith("report-") || s.final).map((s) => s.id);
        expect(tail("own")).toEqual(tail("library"));
        expect(tail("own")).toEqual(["cmp-open", "cmp-author", "cmp-code", "cmp-submit", "report-title", "report-verdict", "done"]);
    });

    it("the chooser lists exactly the two flows", () => {
        expect(TOUR_FLOWS.map((f) => f.flow)).toEqual(["own", "library"]);
        expect(otherFlow("own")).toBe("library");
        expect(otherFlow("library")).toBe("own");
    });
});
