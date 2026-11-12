import type { VarianteMetrica } from "../../lib/api";
import { toPct } from "../../lib/dictamen";

const RADIUS = 20;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function MiniRadial({ variant, animate }: { variant: VarianteMetrica; animate: boolean }) {
    const pct = toPct(variant.gcb_similarity);
    const offset = pct === null ? CIRCUMFERENCE : CIRCUMFERENCE * (1 - (animate ? pct : 0) / 100);
    return (
        <li className="flex items-center gap-2.5 rounded-2xl border border-slate-200 bg-white p-2 dark:border-[#2b3346]/60 dark:bg-[#121827]/40">
            <div className="relative h-12 w-12 shrink-0">
                <svg
                    className="h-full w-full -rotate-90"
                    viewBox="0 0 50 50"
                    role="progressbar"
                    aria-label={`Similitud con ${variant.titulo}`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={pct ?? undefined}
                >
                    <circle cx="25" cy="25" r={RADIUS} className="stroke-slate-100 dark:stroke-[#2b3346]/40" strokeWidth="5" fill="transparent" />
                    {pct !== null && (
                        <circle
                            cx="25" cy="25" r={RADIUS} stroke="#2563eb" strokeWidth="5" fill="transparent"
                            strokeDasharray={CIRCUMFERENCE} strokeDashoffset={offset} strokeLinecap="round"
                            className="transition-all duration-1000 ease-out motion-reduce:transition-none"
                        />
                    )}
                </svg>
                <span className="absolute inset-0 flex items-center justify-center text-[11px] font-extrabold text-slate-900 dark:text-white">
                    {pct === null ? "N/A" : `${pct}%`}
                </span>
            </div>
            <div className="min-w-0">
                <p className="truncate text-xs font-bold text-slate-900 dark:text-white" title={variant.titulo}>
                    {variant.titulo}
                </p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    {pct === null ? `No evaluado (${variant.gcb_estado ?? "sin calcular"})` : "Similitud semántica"}
                </p>
            </div>
        </li>
    );
}

/** Small circles, one per AI variant; the big circle above stays the teacher's reference. */
export function VariantMetrics({ variants, animate }: { variants?: VarianteMetrica[]; animate: boolean }) {
    if (!variants || variants.length === 0) return null;
    return (
        <section aria-labelledby="variant-metrics-title" className="rounded-3xl border border-slate-200 bg-white p-3 shadow-sm dark:border-[#2b3346]/60 dark:bg-[#121827]/40">
            <h3
                id="variant-metrics-title"
                title="Similitud con variantes generadas con IA. La referencia del docente sigue siendo la principal."
                className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400"
            >
                Otras implementaciones (IA)
            </h3>
            <ul className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                {variants.map((v, i) => (
                    <MiniRadial key={v.variante_id ?? `${v.titulo}-${i}`} variant={v} animate={animate} />
                ))}
            </ul>
        </section>
    );
}
