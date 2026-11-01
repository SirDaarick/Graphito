import { describe, expect, it } from "vitest";
import { nextFocusIndex } from "./focusTrap";

describe("nextFocusIndex", () => {
    it("moves forward and wraps from the last control to the first", () => {
        expect(nextFocusIndex(3, 0, false)).toBe(1);
        expect(nextFocusIndex(3, 2, false)).toBe(0);
    });

    it("moves backwards and wraps from the first control to the last", () => {
        expect(nextFocusIndex(3, 2, true)).toBe(1);
        expect(nextFocusIndex(3, 0, true)).toBe(2);
    });

    it("enters the list at the matching end when focus is outside it", () => {
        expect(nextFocusIndex(4, -1, false)).toBe(0);
        expect(nextFocusIndex(4, -1, true)).toBe(3);
    });

    it("returns -1 when there is nothing to focus", () => {
        expect(nextFocusIndex(0, -1, false)).toBe(-1);
    });

    it("stays on the only control", () => {
        expect(nextFocusIndex(1, 0, false)).toBe(0);
        expect(nextFocusIndex(1, 0, true)).toBe(0);
    });
});
