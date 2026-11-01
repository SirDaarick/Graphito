/**
 * Line-level style attribution (occlusion): an approximation of which lines move the CharCNN style
 * score. Each line's `aporte` is p(original) - p(line removed). It is a measurement to read, not a
 * detection or a verdict.
 */

export interface LineaEstilo {
    numero_linea: number;
    aporte: number;
}

export interface StyleAttribution {
    metodo: string;
    probabilidad: number | null;
    lineas: LineaEstilo[];
    aproximacion: boolean;
}

export type StyleIntensity = 1 | 2 | 3;

/** Intensity bucket (1 faint .. 3 strong) per line number, relative to the largest contribution. */
export function styleIntensityByLine(lineas: LineaEstilo[] | undefined | null): Map<number, StyleIntensity> {
    const map = new Map<number, StyleIntensity>();
    const valid = (lineas ?? []).filter(
        (l) => Number.isInteger(l.numero_linea) && l.numero_linea >= 1 && Number.isFinite(l.aporte) && l.aporte > 0
    );
    if (valid.length === 0) return map;
    const max = Math.max(...valid.map((l) => l.aporte));
    for (const l of valid) {
        const ratio = l.aporte / max;
        map.set(l.numero_linea, ratio >= 0.66 ? 3 : ratio >= 0.33 ? 2 : 1);
    }
    return map;
}
