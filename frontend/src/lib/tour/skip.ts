import { matchRoute } from "../router";
import type { TourContext, TourStep } from "./types";

/** What the app looks like right now, as far as skipping a step is concerned. */
export interface TourEnv {
    path: string;
    hasTarget: (name: string) => boolean;
    /** True only on arrival at the step, and only when its highlighted field already has content. */
    filledOnArrival: boolean;
}

/** True when the user already did what the step asks (they got ahead of the guide). */
export function shouldSkipStep(step: TourStep, context: TourContext, env: TourEnv): boolean {
    const skip = step.skipWhen;
    if (!skip) return false;
    if (skip.present?.some((name) => env.hasTarget(name))) return true;
    if (skip.route && matchRoute(skip.route, env.path).isMatch) return true;
    if (skip.problemChosen && context.problemId !== null) return true;
    if (skip.filled && env.filledOnArrival) return true;
    return false;
}
