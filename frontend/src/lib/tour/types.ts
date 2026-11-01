import type { ExampleCase, ExampleSummary } from "../api";

export type TourFlow = "own" | "library" | "examples";

/** Side of the report modal a step needs: the metric cards or the side-by-side code. */
export type TourReportView = "summary" | "code";

export type TourPlacement = "top" | "bottom" | "left" | "right";

/** What moves the tour to the next step. */
export type TourAdvance =
    /**
     * The user clicks the highlighted element. With `untilGone`, the tour waits for
     * the element to disappear after the click, so a failed submit keeps the step.
     */
    | { kind: "click"; untilGone?: boolean }
    /** The highlighted field is filled; the tooltip enables "Siguiente". */
    | { kind: "filled" }
    /** The URL matches the pattern (same syntax as `matchRoute`). */
    | { kind: "route"; pattern: string }
    /** The user presses the tooltip's own button. */
    | { kind: "manual" }
    /**
     * The user clicks any `problem-card` inside the highlighted list; that card's problem becomes the
     * tour's problem. The click is swallowed so the card's own buttons do not also fire.
     */
    | { kind: "pick" };

/** Conditions that mean the user already did what a step asks, so the tour moves past it. Any one is enough. */
export interface TourSkip {
    /** Some of these `data-tour` targets is already on screen (e.g. the modal the step opens is open). */
    present?: string[];
    /** The current path matches this pattern (same syntax as `matchRoute`). */
    route?: string;
    /** The tour already has a problem (created or added by the user). */
    problemChosen?: boolean;
    /** On arrival, the highlighted field already has content. */
    filled?: boolean;
}

export interface TourStep {
    id: string;
    /** Skip the step when the user got ahead of the guide. */
    skipWhen?: TourSkip;
    /** `data-tour` value of the element to highlight. Omitted for a centered card. */
    target?: string;
    title: string;
    text: string;
    placement: TourPlacement;
    advance: TourAdvance;
    /** Step to return to when the target disappears (e.g. the user closed a modal). */
    recoverTo?: string;
    /** Route offered through "Llévame ahí" when the target is not on screen. */
    fallbackRoute?: string;
    /** How long the target may be missing before the tour offers to recover. */
    graceMs?: number;
    /** Prefer the element tagged with the problem created or added during the tour. */
    scopedToProblem?: boolean;
    /** Last card of a flow. */
    final?: boolean;
    /** Route to open when the step starts (e.g. a report); null/absent means stay where the user is. */
    enterRoute?: (context: TourContext) => string | null;
    /** Report modal view to show when the step starts. */
    reportView?: TourReportView;
    /** The library page selects the example group while this step is current. */
    showGroup?: boolean;
    /** The library page expands the submissions list of the problem the teacher picked while this step is current. */
    expandProblem?: boolean;
    /** Examples flow: the step is skipped when the chosen problem has no report of this case. */
    requiresCase?: ExampleCase;
}

export interface TourContext {
    problemId: number | null;
    /** Set only by the examples flow: the group and reports it walks through. */
    examples?: ExampleSummary;
}

export type TourStatus = "idle" | "choosing" | "running";

export interface TourState {
    status: TourStatus;
    flow: TourFlow | null;
    stepIndex: number;
    context: TourContext;
}

export interface Rect {
    top: number;
    left: number;
    width: number;
    height: number;
}

export interface Size {
    width: number;
    height: number;
}
