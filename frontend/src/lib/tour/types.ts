export type TourFlow = "own" | "library";

export type TourPlacement = "top" | "bottom" | "left" | "right";

/** What moves the tour to the next step. */
export type TourAdvance =
    /** The user clicks the highlighted element. */
    | { kind: "click" }
    /** The highlighted field is filled; the tooltip enables "Siguiente". */
    | { kind: "filled" }
    /** The URL matches the pattern (same syntax as `matchRoute`). */
    | { kind: "route"; pattern: string }
    /** The user presses the tooltip's own button. */
    | { kind: "manual" };

export interface TourStep {
    id: string;
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
    /** Prefer the element tagged with the problem created or added during the tour. */
    scopedToProblem?: boolean;
    /** Last card of a flow. */
    final?: boolean;
}

export interface TourContext {
    problemId: number | null;
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
