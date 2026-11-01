import type { ExampleSummary } from "../api";
import { matchRoute } from "../router";
import { getSteps, stepApplies } from "./steps";
import type { TourContext, TourFlow, TourState, TourStep } from "./types";

/** The steps this run will show: the flow's steps minus those the picked problem cannot satisfy. */
function activeSteps(flow: TourFlow, context: TourContext): TourStep[] {
    return getSteps(flow).filter((step) => stepApplies(step, context));
}

export const INITIAL_TOUR_STATE: TourState = {
    status: "idle",
    flow: null,
    stepIndex: 0,
    context: { problemId: null },
};

export type TourAction =
    | { type: "open" }
    /** The examples flow needs the summary of the group it walks through. */
    | { type: "choose"; flow: TourFlow; examples?: ExampleSummary }
    /** `from` makes the advance idempotent: it only applies while that step is still current. */
    | { type: "next"; from?: string }
    | { type: "back" }
    | { type: "goTo"; stepId: string }
    | { type: "exit" }
    | { type: "setProblem"; problemId: number | null }
    /** The teacher picked a problem on a "pick" step: remember it and move on, guarded like `next`. */
    | { type: "pick"; problemId: number; from?: string };

export function tourReducer(state: TourState, action: TourAction): TourState {
    switch (action.type) {
        case "open":
            return { ...INITIAL_TOUR_STATE, status: "choosing" };

        case "choose":
            if (state.status !== "choosing" && state.status !== "running") return state;
            if (action.flow === "examples") {
                if (!action.examples) return state;
                return {
                    status: "running",
                    flow: action.flow,
                    stepIndex: 0,
                    // The teacher picks the problem on the first step.
                    context: { problemId: null, examples: action.examples },
                };
            }
            return { status: "running", flow: action.flow, stepIndex: 0, context: { problemId: null } };

        case "next": {
            if (state.status !== "running" || !state.flow) return state;
            const steps = activeSteps(state.flow, state.context);
            if (action.from !== undefined && steps[state.stepIndex]?.id !== action.from) return state;
            const isLast = state.stepIndex >= steps.length - 1;
            return isLast ? INITIAL_TOUR_STATE : { ...state, stepIndex: state.stepIndex + 1 };
        }

        case "pick": {
            if (state.status !== "running" || !state.flow) return state;
            const current = activeSteps(state.flow, state.context)[state.stepIndex];
            if (current?.advance.kind !== "pick") return state;
            if (action.from !== undefined && current.id !== action.from) return state;
            const context = { ...state.context, problemId: action.problemId };
            // The first step always applies, so its index is the same in the list for the new problem.
            const steps = activeSteps(state.flow, context);
            const isLast = state.stepIndex >= steps.length - 1;
            return isLast ? INITIAL_TOUR_STATE : { ...state, context, stepIndex: state.stepIndex + 1 };
        }

        case "back":
            if (state.status !== "running") return state;
            return { ...state, stepIndex: Math.max(0, state.stepIndex - 1) };

        case "goTo": {
            if (state.status !== "running" || !state.flow) return state;
            const index = activeSteps(state.flow, state.context).findIndex((step) => step.id === action.stepId);
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
    return activeSteps(state.flow, state.context)[state.stepIndex] ?? null;
}

export function stepProgress(state: TourState): { current: number; total: number } {
    if (state.status !== "running" || !state.flow) return { current: 0, total: 0 };
    return { current: state.stepIndex + 1, total: activeSteps(state.flow, state.context).length };
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

/** Route the step opens when it starts, or null when it stays where the user is. */
export function stepEntryPath(step: TourStep, context: TourContext): string | null {
    return step.enterRoute?.(context) ?? null;
}

/** Group the library page must select now: the example group during its showcase step. */
export function tourGroupId(state: TourState): number | null {
    const step = currentStep(state);
    return step?.showGroup ? (state.context.examples?.grupo_id ?? null) : null;
}

/** True when the step advances on a route change and `path` satisfies it. */
export function routeAdvancesStep(step: TourStep, path: string): boolean {
    return step.advance.kind === "route" && matchRoute(step.advance.pattern, path).isMatch;
}
