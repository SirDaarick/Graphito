import { createContext, useContext } from "react";
import type { ExampleSummary } from "../../lib/api";
import type { TourFlow, TourState } from "../../lib/tour/types";

export interface TourApi {
    state: TourState;
    /** True once the user has opened the guide at least once. */
    hasSeen: boolean;
    open: () => void;
    exit: () => void;
    /** The examples flow also needs the summary returned by `api.examples.ensure()`. */
    choose: (flow: TourFlow, examples?: ExampleSummary) => void;
    /** With `fromStepId`, advances only if that step is still the current one. */
    next: (fromStepId?: string) => void;
    back: () => void;
    goTo: (stepId: string) => void;
    /** Remembers the problem created or added during the tour, to highlight its card. */
    setProblem: (problemId: number | null) => void;
    /** Examples flow: the teacher picked a problem on the current step; remember it and advance. */
    pick: (problemId: number, fromStepId?: string) => void;
}

export const TourContext = createContext<TourApi | null>(null);

export function useTour(): TourApi {
    const api = useContext(TourContext);
    if (!api) throw new Error("useTour must be used inside <TourProvider>");
    return api;
}
