import { useEffect, useState } from "react";
import type { Rect } from "../../lib/tour/types";

/** Breathing room between the highlighted element and the spotlight edge. */
export const SPOTLIGHT_PADDING = 6;

export interface TrackedTarget {
    element: HTMLElement | null;
    /** Spotlight rectangle in viewport coordinates, padding included. */
    rect: Rect | null;
    radius: number;
    /** A target was requested but is not (yet) on screen. */
    missing: boolean;
}

/** Tracked data is tagged with its step so a stale value never leaks into the next one. */
interface TrackedState extends TrackedTarget {
    stepKey: string | null;
}

const NO_TARGET: TrackedTarget = { element: null, rect: null, radius: 0, missing: false };

/**
 * An element can have a real box and still be invisible: inside a collapsed
 * accordion (zero-size clipping ancestor) or faded out (opacity 0). Being merely
 * scrolled out of a container does not count as hidden, so it can be scrolled to.
 */
function isShown(element: HTMLElement): boolean {
    const box = element.getBoundingClientRect();
    if (box.width <= 0 || box.height <= 0) return false;

    for (let node: HTMLElement | null = element; node && node !== document.body; node = node.parentElement) {
        const style = getComputedStyle(node);
        if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
        if (node !== element && (style.overflowX !== "visible" || style.overflowY !== "visible")) {
            const clip = node.getBoundingClientRect();
            if (clip.width <= 1 || clip.height <= 1) return false;
        }
    }
    return true;
}

function findVisible(selectors: string[]): HTMLElement | null {
    for (const selector of selectors) {
        for (const node of Array.from(document.querySelectorAll<HTMLElement>(selector))) {
            if (isShown(node)) return node;
        }
    }
    return null;
}

function scrollIntoViewIfNeeded(element: HTMLElement) {
    const box = element.getBoundingClientRect();
    if (box.top >= 0 && box.bottom <= window.innerHeight) return;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    element.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
}

/**
 * Follows the first visible element matching `selectors` once per frame, so the
 * spotlight survives modal animations, scrolling, resizes and layout shifts.
 * With no selectors the step is a centered card and nothing is tracked.
 */
export function useTourTarget(selectors: string[], stepKey: string | null): TrackedTarget {
    const [tracked, setTracked] = useState<TrackedState>({ ...NO_TARGET, stepKey: null });

    useEffect(() => {
        if (!stepKey || selectors.length === 0) {
            setTracked({ ...NO_TARGET, stepKey });
            return;
        }

        let frame = 0;
        let lastElement: HTMLElement | null = null;
        let radius = 0;

        const tick = () => {
            const element = findVisible(selectors);
            if (!element) {
                lastElement = null;
                setTracked((prev) =>
                    prev.stepKey === stepKey && prev.missing ? prev : { ...NO_TARGET, missing: true, stepKey }
                );
            } else {
                if (element !== lastElement) {
                    lastElement = element;
                    radius = parseFloat(getComputedStyle(element).borderTopLeftRadius) || 0;
                    scrollIntoViewIfNeeded(element);
                }
                const box = element.getBoundingClientRect();
                const rect: Rect = {
                    top: box.top - SPOTLIGHT_PADDING,
                    left: box.left - SPOTLIGHT_PADDING,
                    width: box.width + SPOTLIGHT_PADDING * 2,
                    height: box.height + SPOTLIGHT_PADDING * 2,
                };
                setTracked((prev) =>
                    prev.stepKey === stepKey &&
                    prev.element === element &&
                    prev.rect?.top === rect.top &&
                    prev.rect?.left === rect.left &&
                    prev.rect?.width === rect.width &&
                    prev.rect?.height === rect.height
                        ? prev
                        : { stepKey, element, rect, radius: radius + SPOTLIGHT_PADDING, missing: false }
                );
            }
            frame = requestAnimationFrame(tick);
        };

        tick();
        return () => cancelAnimationFrame(frame);
    }, [selectors, stepKey]);

    return tracked.stepKey === stepKey ? tracked : NO_TARGET;
}
