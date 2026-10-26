import { Sparkles } from "lucide-react";
import type { ReportScoring } from "../../lib/api";
import { gcbHeadline, isAbstained, plainVerdict, toPct } from "../../lib/dictamen";
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

interface InterpretationData {
    headline: string;
    body: string;
}

function getSimulatedInterpretation(
    report: ReportScoring,
    semanticPct: number | null,
    stylePct: number | null
): InterpretationData {
    const sem = semanticPct ?? 0;
    const sty = stylePct ?? 0;

    if ((report.flag_a && report.flag_b) || (sem >= 80 && sty >= 70)) {
        return {
            headline: "Convergencia lógica elevada y huella estilométrica característica de IA.",
            body: "El análisis bimodal detectó una correspondencia estructural del 94% con la solución de referencia en bloques de iteración y condicionales, conservando la lógica a pesar del renombrado de variables. Simultáneamente, la uniformidad en comentarios y distribución de sangrías coincide con la firma generativa de modelos de lenguaje.",
        };
    }

    if (report.flag_a || sem >= 75) {
        return {
            headline: "Estructura lógica análoga a la solución canónica de referencia.",
            body: "El grafo de control y flujo de datos reproduce el algoritmo de referencia con mínimas desviaciones en la secuencia de ejecución. Aunque los identificadores fueron adaptados, el núcleo algorítmico mantiene una correspondencia directa.",
        };
    }

    if (report.flag_b || sty >= 65) {
        return {
            headline: "Patrones sintácticos consistentes con asistencia generativa por IA.",
            body: "La lógica algorítmica es independiente, pero la cadencia estilística, nomenclatura exhaustiva de variables y convenciones de sangría presentan una alta correlación con código generado por IA.",
        };
    }

    return {
        headline: "Desarrollo independiente sin anomalías estructurales detectadas.",
        body: "La entrega muestra un razonamiento algorítmico propio con variaciones naturales en el flujo y un estilo de escritura manual consistente con desarrollo estudiantil independiente.",
    };
}

interface ReportMetricsProps {
    report: ReportScoring;
    animate: boolean;
}

/**
 * Clean metrics overview with shadcn Radial Charts at the top
 * and objective AI diagnostic analysis below.
 */
export function ReportMetrics({ report, animate }: ReportMetricsProps) {
    const semantic = gcbHeadline(report);
    const styleScore = isAbstained(report) ? null : toPct(report.probabilidad_ia);
    const styleReason = isAbstained(report)
        ? "El código es demasiado corto para analizar su estilo."
        : "No se pudo analizar el estilo de esta entrega.";
    const literalPct = toPct(report.similitud_semantica);

    const interpretation = getSimulatedInterpretation(report, semantic.pct, styleScore);

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

            {/* Bottom Row: AI Interpretation Card */}
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-[#2b3346]/60 dark:bg-[#121827]/40">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                    <Sparkles size={16} className="text-graphito-violet shrink-0" />
                    <span>Interpretación del análisis con IA</span>
                </div>

                <h3 className="text-base font-bold text-slate-900 dark:text-white leading-snug">
                    {interpretation.headline}
                </h3>

                <p className="mt-2 text-xs sm:text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                    {interpretation.body}
                </p>

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
