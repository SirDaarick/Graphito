import { Info } from "lucide-react";
import type { ReportScoring } from "../../lib/api";
import { gcbHeadline, isAbstained, toPct, VALIDATION_LABEL } from "../../lib/dictamen";
import { InfoPopover } from "../ui/InfoPopover";
import { RadialProgressCard } from "./RadialProgressCard";

function SemanticHelp() {
    return (
        <div className="space-y-3 text-xs leading-relaxed">
            <div>
                <span className="font-bold text-slate-900 dark:text-white block mb-0.5">
                    ¿Qué evalúa?
                </span>
                <p className="text-slate-600 dark:text-slate-300">
                    Compara la lógica y flujo del programa con la solución de referencia mediante GraphCodeBERT, normalizando nombres de variables y funciones.
                </p>
            </div>
            <div>
                <span className="font-bold text-slate-900 dark:text-white block mb-0.5">
                    Interpretación
                </span>
                <p className="text-slate-600 dark:text-slate-300">
                    0% representa algoritmos distintos; cercano a 100% indica implementación idéntica.
                </p>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 italic border-t border-slate-200 dark:border-slate-800 pt-2">
                Medición exploratoria de apoyo a la docencia.
            </p>
        </div>
    );
}

function StyleHelp() {
    return (
        <div className="space-y-3 text-xs leading-relaxed">
            <div>
                <span className="font-bold text-slate-900 dark:text-white block mb-0.5">
                    ¿Qué evalúa?
                </span>
                <p className="text-slate-600 dark:text-slate-300">
                    Analiza patrones de sintaxis, sangría y estructura de caracteres (CharCNN) contrastados con código generado por IA.
                </p>
            </div>
            <div>
                <span className="font-bold text-slate-900 dark:text-white block mb-0.5">
                    Interpretación
                </span>
                <p className="text-slate-600 dark:text-slate-300">
                    A mayor porcentaje, mayor cercanía estilística con código generado por modelos de lenguaje.
                </p>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 italic border-t border-slate-200 dark:border-slate-800 pt-2">
                Entregas muy breves se abstienen para evitar falsos positivos.
            </p>
        </div>
    );
}

function LiteralHelp() {
    return (
        <div className="space-y-2 text-xs leading-relaxed">
            <span className="font-bold text-slate-900 dark:text-white block mb-0.5">
                ¿Qué evalúa?
            </span>
            <p className="text-slate-600 dark:text-slate-300">
                Mide fragmentos consecutivos de 5 tokens compartidos exactamente con la referencia (Jaccard léxico).
            </p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 italic border-t border-slate-200 dark:border-slate-800 pt-1.5">
                Detecta copia textual directa sin considerar la estructura lógica.
            </p>
        </div>
    );
}

interface ReportMetricsProps {
    report: ReportScoring;
    animate: boolean;
}

/**
 * Clean metrics overview with shadcn Radial Charts at the top
 * and plain context on how to read them below (no conclusion about the student).
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
                <RadialProgressCard
                    title="Similitud semántica"
                    centerLabel="Lógica"
                    pct={semantic.pct}
                    unavailableReason={semantic.reason}
                    description="Qué tan parecida es la lógica frente a la referencia, aun si cambian nombres."
                    helpLabel="Cómo se calcula la similitud semántica"
                    helpTitle="Similitud semántica"
                    help={<SemanticHelp />}
                    accent="blue"
                    animate={animate}
                />

                <RadialProgressCard
                    title="Estilo del código"
                    centerLabel="Prob. IA"
                    pct={styleScore}
                    unavailableReason={styleReason}
                    description="Qué tan parecida es la forma de escribir frente a código generado por IA."
                    helpLabel="Cómo se calcula el estilo del código"
                    helpTitle="Estilo del código"
                    help={<StyleHelp />}
                    accent="violet"
                    animate={animate}
                />
            </div>

            {/* Bottom Row: how to read the numbers. Context only; the teacher decides what they mean. */}
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-[#2b3346]/60 dark:bg-[#121827]/40">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                    <Info size={16} className="text-graphito-blue shrink-0" aria-hidden="true" />
                    <h3>Cómo leer estas métricas</h3>
                </div>

                <ul className="space-y-2 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed list-disc pl-4">
                    <li>
                        <strong className="font-semibold text-slate-800 dark:text-slate-100">Similitud semántica</strong>{" "}
                        mide cuánto se parece la lógica a la solución de referencia. Una solución correcta también
                        se parece a la referencia, así que un valor alto no indica por sí solo un problema.
                    </li>
                    <li>
                        <strong className="font-semibold text-slate-800 dark:text-slate-100">Estilo del código</strong>{" "}
                        mide la cercanía de la escritura con código generado por modelos de lenguaje. Quien escribe
                        de forma ordenada o con ayuda de un editor también puede acercarse a ese estilo.
                    </li>
                </ul>

                <p className="mt-3 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                    Los modelos pueden equivocarse, y estas cifras no son evidencia concluyente sobre ninguna entrega.
                    Qué significan y qué hacer con ellas lo decide el docente.
                </p>
                <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400 italic">{VALIDATION_LABEL}</p>
                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-[#2b3346]/40 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
                        <span>
                            Coincidencia literal de texto:{" "}
                            <span className="font-semibold text-slate-700 dark:text-slate-300">
                                {literalPct === null ? "no disponible" : `${literalPct} %`}
                            </span>
                        </span>
                        <InfoPopover label="Cómo se calcula la coincidencia literal" title="Coincidencia literal de texto">
                            <LiteralHelp />
                        </InfoPopover>
                    </div>
                </div>
            </div>
        </div>
    );
}
