import { describe, expect, it } from "vitest";
import { styleIntensityByLine } from "./styleAttribution";

describe("styleIntensityByLine", () => {
    it("returns an empty map without attribution", () => {
        expect(styleIntensityByLine(undefined).size).toBe(0);
        expect(styleIntensityByLine([]).size).toBe(0);
    });

    it("buckets each contribution relative to the largest one", () => {
        const map = styleIntensityByLine([
            { numero_linea: 3, aporte: 0.1 },
            { numero_linea: 8, aporte: 0.06 },
            { numero_linea: 12, aporte: 0.02 },
        ]);
        expect(map.get(3)).toBe(3);
        expect(map.get(8)).toBe(2);
        expect(map.get(12)).toBe(1);
    });

    it("ignores zero, negative and non-finite contributions and invalid line numbers", () => {
        const map = styleIntensityByLine([
            { numero_linea: 1, aporte: 0 },
            { numero_linea: 2, aporte: -0.05 },
            { numero_linea: 3, aporte: Number.NaN },
            { numero_linea: 0, aporte: 0.2 },
            { numero_linea: 5, aporte: 0.04 },
        ]);
        expect([...map.keys()]).toEqual([5]);
        expect(map.get(5)).toBe(3);
    });
});
