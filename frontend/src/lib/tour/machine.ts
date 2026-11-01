import { matchRoute } from "../router";
import { getSteps } from "./steps";
import type { TourContext, TourFlow, TourState, TourStep } from "./types";

export const INITIAL_TOUR_STATE: TourState = {
    status: "idle",
    flow: null,
    stepIndex: 0,
    context: { problemId: null },
};

export type TourAction =
    | { type: "open" }
    | { type: "choose"; flow: TourFlow }
    | { type: "next" }
    | { type: "back" }
    | { type: "goTo"; stepId: string }
    | { type: "exit" }
    | { type: "setProblem"; problemId: number | null };

export function tourReducer(state: TourState, action: TourAction): TourState {
    switch (action.type) {
        case "open":
            return { ...INITIAL_TOUR_STATE, status: "choosing" };

        case "choose":
            if (state.status !== "choosing" && state.status !== "running") return state;
            return { status: "running", flow: action.flow, stepIndex: 0, context: { problemId: null } };

        case "next": {
            if (state.status !== "running" || !state.flow) return state;
            const isLast = state.stepIndex >= getSteps(state.flow).length - 1;
            return isLast ? INITIAL_TOUR_STATE : { ...state, stepIndex: state.stepIndex + 1 };
        }

        case "back":
            if (state.status !== "running") return state;
            return { ...state, stepIndex: Math.max(0, state.stepIndex - 1) };

        case "goTo": {
            if (state.status !== "running" || !state.flow) return state;
            const index = getSteps(state.flow).findIndex((step) => step.id === action.stepId);
            return index < 0 ? state : { ...state, stepIndex: index };
        }

        case "exit":
            return INITIAL_TOUR_STATE;

        case "setProblem":
            if (state.status !== "running") return state;
            return { ...state, context: { ...state.context, problemId: action.problemId } };

        default:
            return state;
    }
}

export function currentStep(state: TourState): TourStep | null {
    if (state.status !== "running" || !state.flow) return null;
    return getSteps(state.flow)[state.stepIndex] ?? null;
}

export function stepProgress(state: TourState): { current: number; total: number } {
    if (state.status !== "running" || !state.flow) return { current: 0, total: 0 };
    return { current: state.stepIndex + 1, total: getSteps(state.flow).length };
}

/** CSS selectors for the step target, most specific first. */
export function resolveTargetSelectors(step: TourStep, context: TourContext): string[] {
    if (!step.target) return [];
    const base = `[data-tour="${step.target}"]`;
    if (step.scopedToProblem && context.problemId !== null) {
        return [`${base}[data-problem-id="${context.problemId}"]`, base];
    }
    return [base];
}

/** True when the step advances on a route change and `path` satisfies it. */
export function routeAdvancesStep(step: TourStep, path: string): boolean {
    return step.advance.kind === "route" && matchRoute(step.advance.pattern, path).isMatch;
}
