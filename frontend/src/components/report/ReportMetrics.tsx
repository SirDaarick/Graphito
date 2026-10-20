import type { ReportScoring } from "../../lib/api";
import { gcbHeadline, isAbstained, plainVerdict, toPct, type VerdictTone } from "../../lib/dictamen";
import { InfoPopover, InfoSection } from "../ui/InfoPopover";
import { MetricCard } from "./MetricCard";

const TONE_STYLES: Record<VerdictTone, string> = {
    dual: "border-rose-500/30 bg-rose-500/10 text-rose-800 dark:text-rose-200",
    semantic: "border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200",
    stylometric: "border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200",
    clear: "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200",
    neutral: "border-slate-400/30 bg-slate-500/10 text-slate-700 dark:text-slate-300",
    pending: "border-slate-400/30 bg-slate-500/10 text-slate-700 dark:text-slate-300",
};

function Risks({ items }: { items: string[] }) {
    return (
        <ul className="list-disc space-y-1 pl-4">
            {items.map((item) => (
                <li key={item}>{item}</li>
            ))}
        </ul>
    );
}

function SemanticHelp() {
    return (
        <>
            <InfoSection heading="Qué toma en cuenta">
                <p>
                    Qué hace el programa, no cómo está escrito. Un modelo de lenguaje para código (GraphCodeBERT) lee la entrega y la
                    solución de referencia. Antes de leerlas se uniforman los nombres de variables y funciones, así que cambiarlos no
                    baja el porcentaje.
                </p>
            </InfoSection>
            <InfoSection heading="Cómo se obtiene">
                <p>
                    Cada código se convierte en una huella numérica y se mide qué tan cercanas son. Se muestra la referencia más
                    parecida: 0 % es nada en común y 100 % es prácticamente la misma lógica.
                </p>
            </InfoSection>
            <InfoSection heading="Riesgos y límites">
                <Risks
                    items={[
                        "Es una medición exploratoria: el modelo no fue entrenado ni calibrado para este curso y no tiene un umbral validado.",
                        "Por eso nunca genera una alerta por sí sola. La alerta de la plataforma se basa en las otras dos señales (coincidencia literal y estilo).",
                        "Puede salir alta en ejercicios simples o muy comunes, como ordenar o Fibonacci, donde casi todos escriben algo parecido.",
                        "Depende de las referencias cargadas: con pocas o poco representativas, el resultado cambia.",
                        "Un porcentaje alto no prueba una copia; es un motivo para revisar el código.",
                    ]}
                />
            </InfoSection>
        </>
    );
}

function StyleHelp() {
    return (
        <>
            <InfoSection heading="Qué toma en cuenta">
                <p>
                    La forma de escribir el código: sangrías, nombres, comentarios y espacios. Un modelo de caracteres (CharCNN)
                    aprendió a distinguir código escrito por personas del generado por IA.
                </p>
            </InfoSection>
            <InfoSection heading="Cómo se obtiene">
                <p>
                    Lee el código carácter por carácter y devuelve un puntaje de 0 % a 100 %: cuanto más alto, más se parece su estilo
                    al del código generado por IA. El puntaje se ajusta con ejemplos para que sea comparable entre entregas. Esta señal
                    sí interviene en la alerta de la plataforma.
                </p>
            </InfoSection>
            <InfoSection heading="Riesgos y límites">
                <Risks
                    items={[
                        "Puede fallar con códigos muy cortos; en ese caso se abstiene y no muestra porcentaje.",
                        "Puede confundir código muy ordenado, como el de un docente o un libro de texto, con código generado.",
                        "Formateadores automáticos o plantillas pueden hacer que un código humano parezca generado.",
                        "No indica quién escribió el código, solo qué tan parecido es su estilo.",
                    ]}
                />
            </InfoSection>
        </>
    );
}

function LiteralHelp() {
    return (
        <>
            <InfoSection heading="Qué toma en cuenta">
                <p>Cuántos fragmentos consecutivos de 5 elementos del código (palabras y símbolos) aparecen igual en la referencia.</p>
            </InfoSection>
            <InfoSection heading="Cómo se obtiene">
                <p>
                    Se normaliza el código, se parte en fragmentos de 5 elementos y se mide qué proporción comparten ambos códigos
                    (índice de Jaccard).
                </p>
            </InfoSection>
            <InfoSection heading="Riesgos y límites">
                <Risks
                    items={[
                        "Solo ve texto: renombrar variables o reordenar instrucciones la engaña, y no entiende lo que hace el programa.",
                        "Se muestra solo como referencia. Aun así interviene en la alerta de la plataforma, junto con el estilo.",
                    ]}
                />
            </InfoSection>
        </>
    );
}

interface ReportMetricsProps {
    report: ReportScoring;
    animate: boolean;
}

/** Verdict sentence plus the metric cards: GraphCodeBERT first, style second, literal match as a small reference. */
export function ReportMetrics({ report, animate }: ReportMetricsProps) {
    const verdict = plainVerdict(report.dictamen, report.estado);
    const semantic = gcbHeadline(report);
    const styleScore = isAbstained(report) ? null : toPct(report.probabilidad_ia);
    const styleReason = isAbstained(report)
        ? "El código es demasiado corto para analizar su estilo."
        : "No se pudo analizar el estilo de esta entrega.";
    const literalPct = toPct(report.similitud_semantica);

    return (
        <div className="flex flex-col gap-4">
            <div className={`rounded-2xl border px-4 py-3 ${TONE_STYLES[verdict.tone]}`} role="status">
                <p className="text-sm font-semibold leading-snug">{verdict.text}</p>
                <p className="mt-1 text-xs opacity-80">Apoya la revisión; la decisión final es del docente.</p>
            </div>

            <MetricCard
                title="Similitud semántica"
                pct={semantic.pct}
                unavailableReason={semantic.reason}
                description="Qué tan parecida es la lógica de la entrega a la de las soluciones de referencia, aunque cambien los nombres."
                helpLabel="Cómo se calcula la similitud semántica"
                helpTitle="Similitud semántica"
                help={<SemanticHelp />}
                accent="blue"
                animate={animate}
            />

            <MetricCard
                title="Estilo del código"
                pct={styleScore}
                unavailableReason={styleReason}
                description="Qué tan parecida es la forma de escribir el código a la de código generado por IA."
                helpLabel="Cómo se calcula el estilo del código"
                helpTitle="Estilo del código"
                help={<StyleHelp />}
                accent="violet"
                animate={animate}
            />

            <div className="flex items-center justify-between gap-2 px-2 text-xs text-slate-500 dark:text-slate-400">
                <span>
                    Coincidencia literal de texto:{" "}
                    <span className="font-semibold text-slate-600 dark:text-slate-300">{literalPct === null ? "no disponible" : `${literalPct} %`}</span>
                </span>
                <InfoPopover label="Cómo se calcula la coincidencia literal" title="Coincidencia literal de texto">
                    <LiteralHelp />
                </InfoPopover>
            </div>
        </div>
    );
}
