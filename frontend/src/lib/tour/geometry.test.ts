import { describe, expect, it } from "vitest";
import { computeTooltipPosition } from "./geometry";

const viewport = { width: 1000, height: 700 };
const tooltip = { width: 300, height: 120 };

describe("computeTooltipPosition", () => {
    it("places the tooltip on the preferred side, centered on the target", () => {
        const pos = computeTooltipPosition({ top: 300, left: 400, width: 100, height: 40 }, tooltip, viewport, "bottom");
        expect(pos.placement).toBe("bottom");
        expect(pos.top).toBe(300 + 40 + 16);
        expect(pos.left).toBe(450 - 150);
        expect(pos.arrowOffset).toBe(150);
    });

    it("flips to the opposite side when the preferred one does not fit", () => {
        const pos = computeTooltipPosition({ top: 640, left: 400, width: 100, height: 40 }, tooltip, viewport, "bottom");
        expect(pos.placement).toBe("top");
        expect(pos.top).toBe(640 - 120 - 16);
    });

    it("keeps the tooltip inside the viewport horizontally and points the arrow at the target", () => {
        const pos = computeTooltipPosition({ top: 300, left: 10, width: 40, height: 40 }, tooltip, viewport, "bottom");
        expect(pos.left).toBe(12);
        // Target center (30) is 18px from the tooltip edge; the arrow never goes closer than 20px.
        expect(pos.arrowOffset).toBe(20);
    });

    it("uses a side placement when asked and it fits", () => {
        const pos = computeTooltipPosition({ top: 200, left: 100, width: 200, height: 100 }, tooltip, viewport, "right");
        expect(pos.placement).toBe("right");
        expect(pos.left).toBe(100 + 200 + 16);
        expect(pos.top).toBe(250 - 60);
    });

    it("stays on screen when the target is larger than the viewport", () => {
        const pos = computeTooltipPosition({ top: 0, left: 0, width: 1000, height: 700 }, tooltip, viewport, "bottom");
        expect(pos.top).toBeGreaterThanOrEqual(12);
        expect(pos.top + tooltip.height).toBeLessThanOrEqual(viewport.height - 12);
        expect(pos.left).toBeGreaterThanOrEqual(12);
    });
});
