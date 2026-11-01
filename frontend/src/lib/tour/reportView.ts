import type { TourReportView } from "./types";

/** Dispatched on `window` when a tour step needs a given view of the open report modal. */
export const TOUR_REPORT_VIEW_EVENT = "graphito:tour-report-view";

export function requestReportView(view: TourReportView): void {
    if (typeof window === "undefined") return;
    window.dispatchEvent(new CustomEvent<TourReportView>(TOUR_REPORT_VIEW_EVENT, { detail: view }));
}
