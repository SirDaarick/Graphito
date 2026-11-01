import type { ReportScoring } from "../../lib/api";
import { gcbHeadline, isAbstained, toPct } from "../../lib/dictamen";
import { InfoPopover } from "../ui/InfoPopover";
import { RadialProgressCard } from "./RadialProgressCard";

function HelpText({ what, how }: { what: string; how: string }) {
    return (
        <div className="space-y-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
            <p>{what}</p>
            <p>{how}</p>
        </div>
    );
}

function SemanticHelp() {
    return (
        <HelpText
            what="Compara cómo está pensada la solución con la de referencia, aunque cambien los nombres."
            how="Cerca de 0 % son soluciones distintas; cerca de 100 % son casi la misma."
        />
    );
}

function StyleHelp() {
    return (
        <HelpText
            what="Mide qué tanto se parece la forma de escribir el código a la de un programa generado por IA."
            how="Un porcentaje alto no prueba nada por sí solo: quien programa con orden también puede parecerse."
        />
    );
}

function LiteralHelp() {
    return (
        <HelpText
            what="Mide cuánto texto del código es idéntico al de la referencia."
            how="Sirve para detectar copias directas."
        />
    );
}

interface ReportMetricsProps {
    report: ReportScoring;
    animate: boolean;
}

/**
 * The two scores that matter, in plain language, plus one line of context
 * (no conclusion about the student).
 */
export function ReportMetrics({ report, animate }: ReportMetricsProps) {
    const semantic = gcbHeadline(report);
    const styleScore = isAbstained(report) ? null : toPct(report.probabilidad_ia);
    const styleReason = isAbstained(report)
        ? "El código es demasiado corto para analizar su estilo."
        : "No se pudo analizar el estilo de esta entrega.";
    const literalPct = toPct(report.similitud_semantica);

    return (
        <div className="flex flex-col gap-4">
            {/* Top Row: Two Radial Progress Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* The wrappers are guided-tour anchors; they stretch the card like a direct grid child. */}
                <div data-tour="metric-semantic" className="flex flex-col rounded-3xl [&>article]:flex-1">
                    <RadialProgressCard
                        title="Similitud semántica"
                        centerLabel="Lógica"
                        pct={semantic.pct}
                        unavailableReason={semantic.reason}
                        description="Qué tan parecida es la solución a la referencia."
                        helpLabel="Cómo se calcula la similitud semántica"
                        helpTitle="Similitud semántica"
                        help={<SemanticHelp />}
                        accent="blue"
                        animate={animate}
                    />
                </div>

                <div data-tour="metric-style" className="flex flex-col rounded-3xl [&>article]:flex-1">
                    <RadialProgressCard
                        title="Estilo del código"
                        centerLabel="Prob. IA"
                        pct={styleScore}
                        unavailableReason={styleReason}
                        description="Qué tanto se parece a código generado por IA."
                        helpLabel="Cómo se calcula el estilo del código"
                        helpTitle="Estilo del código"
                        help={<StyleHelp />}
                        accent="violet"
                        animate={animate}
                    />
                </div>
            </div>

            {/* Short context only; the teacher decides what the numbers mean. */}
            <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 dark:border-[#2b3346]/60 dark:bg-[#121827]/40">
                <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                    Son medidas de apoyo y pueden equivocarse: no prueban nada por sí solas. La decisión es tuya.
                </p>
                <div data-tour="metric-literal" className="mt-3 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <span>
                        Texto idéntico a la referencia:{" "}
                        <span className="font-semibold text-slate-700 dark:text-slate-300">
                            {literalPct === null ? "no disponible" : `${literalPct} %`}
                        </span>
                    </span>
                    <InfoPopover label="Qué es el texto idéntico" title="Texto idéntico">
                        <LiteralHelp />
                    </InfoPopover>
                </div>
            </div>
        </div>
    );
}
