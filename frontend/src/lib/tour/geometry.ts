import type { Rect, Size, TourPlacement } from "./types";

export interface TooltipPosition {
    top: number;
    left: number;
    placement: TourPlacement;
    /** Distance of the arrow tip from the tooltip's own edge, along the target axis. */
    arrowOffset: number;
}

const OPPOSITE: Record<TourPlacement, TourPlacement> = {
    top: "bottom",
    bottom: "top",
    left: "right",
    right: "left",
};

const ARROW_INSET = 20;

function clamp(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), Math.max(min, max));
}

function placeAt(target: Rect, tooltip: Size, viewport: Size, placement: TourPlacement, gap: number, margin: number) {
    const centerX = target.left + target.width / 2;
    const centerY = target.top + target.height / 2;

    if (placement === "top" || placement === "bottom") {
        return {
            left: clamp(centerX - tooltip.width / 2, margin, viewport.width - tooltip.width - margin),
            top: placement === "top" ? target.top - tooltip.height - gap : target.top + target.height + gap,
        };
    }
    return {
        top: clamp(centerY - tooltip.height / 2, margin, viewport.height - tooltip.height - margin),
        left: placement === "left" ? target.left - tooltip.width - gap : target.left + target.width + gap,
    };
}

function fits(pos: { top: number; left: number }, tooltip: Size, viewport: Size, margin: number): boolean {
    return (
        pos.top >= margin &&
        pos.left >= margin &&
        pos.top + tooltip.height <= viewport.height - margin &&
        pos.left + tooltip.width <= viewport.width - margin
    );
}

/**
 * Places the tooltip next to the target on the preferred side, flipping to the
 * opposite or an adjacent side when it would leave the viewport.
 */
export function computeTooltipPosition(
    target: Rect,
    tooltip: Size,
    viewport: Size,
    preferred: TourPlacement,
    gap = 16,
    margin = 12
): TooltipPosition {
    const sides = Array.from(
        new Set<TourPlacement>([
            preferred,
            OPPOSITE[preferred],
            ...(preferred === "top" || preferred === "bottom"
                ? (["right", "left"] as TourPlacement[])
                : (["bottom", "top"] as TourPlacement[])),
        ])
    );

    let chosen = sides.find((side) => fits(placeAt(target, tooltip, viewport, side, gap, margin), tooltip, viewport, margin));
    let pos = chosen ? placeAt(target, tooltip, viewport, chosen, gap, margin) : null;

    if (!chosen || !pos) {
        // Nothing fits (large target on a small screen): keep the preferred side and stay on screen.
        chosen = preferred;
        const raw = placeAt(target, tooltip, viewport, preferred, gap, margin);
        pos = {
            top: clamp(raw.top, margin, viewport.height - tooltip.height - margin),
            left: clamp(raw.left, margin, viewport.width - tooltip.width - margin),
        };
    }

    const horizontal = chosen === "top" || chosen === "bottom";
    const targetCenter = horizontal ? target.left + target.width / 2 : target.top + target.height / 2;
    const origin = horizontal ? pos.left : pos.top;
    const length = horizontal ? tooltip.width : tooltip.height;
    const arrowOffset = clamp(targetCenter - origin, ARROW_INSET, length - ARROW_INSET);

    return { top: pos.top, left: pos.left, placement: chosen, arrowOffset };
}
