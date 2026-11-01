import type { ExampleCase } from "../api";
import type { TourContext, TourFlow, TourStep } from "./types";

const OWN_EXERCISE_STEPS: TourStep[] = [
    {
        id: "own-new-code",
        target: "header-new-code",
        title: "Crea tu ejercicio",
        text: "Pulsa «Nuevo código» para registrar tu solución de referencia.",
        placement: "bottom",
        advance: { kind: "click" },
    },
    {
        id: "own-title",
        target: "ref-title",
        title: "Ponle un nombre",
        text: "Por ejemplo: «Búsqueda binaria».",
        placement: "bottom",
        advance: { kind: "filled" },
        recoverTo: "own-new-code",
    },
    {
        id: "own-code",
        target: "ref-code",
        title: "Agrega el código",
        text: "Sube un archivo .c o .cpp, o pega el código.",
        placement: "right",
        advance: { kind: "filled" },
        recoverTo: "own-new-code",
    },
    {
        id: "own-submit",
        target: "ref-submit",
        title: "Guárdalo",
        text: "Pulsa «Agregar código de referencia».",
        placement: "top",
        advance: { kind: "click", untilGone: true },
        recoverTo: "own-new-code",
    },
];

const LIBRARY_STEPS: TourStep[] = [
    {
        id: "lib-catalog",
        target: "nav-catalog",
        title: "Abre el catálogo",
        text: "Aquí están los ejercicios precargados.",
        placement: "bottom",
        advance: { kind: "route", pattern: "/catalogo" },
        fallbackRoute: "/catalogo",
    },
    {
        id: "lib-expand",
        target: "catalog-expand-all",
        title: "Despliega los programas",
        text: "Muestra todas las materias y unidades.",
        placement: "bottom",
        advance: { kind: "click" },
        recoverTo: "lib-catalog",
    },
    {
        id: "lib-program",
        target: "catalog-program",
        title: "Elige un programa",
        text: "Haz clic en cualquiera para ver su código.",
        placement: "top",
        advance: { kind: "click" },
        recoverTo: "lib-expand",
    },
    {
        id: "lib-add",
        target: "catalog-add",
        title: "Agrégalo a tu biblioteca",
        text: "Se usará como solución de referencia.",
        placement: "top",
        advance: { kind: "click", untilGone: true },
        recoverTo: "lib-program",
    },
    {
        id: "lib-go",
        target: "catalog-go-library",
        title: "Vuelve a tu biblioteca",
        text: "Pulsa «Ir a la biblioteca».",
        placement: "top",
        advance: { kind: "route", pattern: "/biblioteca" },
        graceMs: 10000,
        recoverTo: "lib-program",
    },
];

/** Shared by both flows: compare a submission and read the report. */
const SHARED_TAIL: TourStep[] = [
    {
        id: "cmp-open",
        target: "compare",
        title: "Compara una entrega",
        text: "Pulsa «Comparar» en tu ejercicio.",
        placement: "bottom",
        advance: { kind: "click" },
        scopedToProblem: true,
        fallbackRoute: "/biblioteca",
    },
    {
        id: "cmp-author",
        target: "cmp-author",
        title: "Identifica al alumno",
        text: "Escribe su nombre o boleta.",
        placement: "bottom",
        advance: { kind: "filled" },
        recoverTo: "cmp-open",
    },
    {
        id: "cmp-code",
        target: "cmp-code",
        title: "Sube su código",
        text: "Un archivo .c o .cpp, o pégalo aquí.",
        placement: "top",
        advance: { kind: "filled" },
        recoverTo: "cmp-open",
    },
    {
        id: "cmp-submit",
        target: "cmp-submit",
        title: "Inicia el análisis",
        text: "Se comparará contra tu referencia.",
        placement: "top",
        advance: { kind: "route", pattern: "/reporte/:id" },
        recoverTo: "cmp-open",
    },
    {
        id: "report-title",
        target: "report-title",
        title: "Este es el resultado",
        text: "El sistema orienta, pero la decisión final es tuya.",
        placement: "bottom",
        advance: { kind: "manual" },
        recoverTo: "cmp-open",
    },
    {
        id: "report-verdict",
        target: "report-verdict",
        title: "Registra tu decisión",
        text: "Marca la entrega sin observaciones o para aclarar con el alumno.",
        placement: "top",
        advance: { kind: "click" },
        recoverTo: "cmp-open",
    },
    {
        id: "done",
        title: "¡Listo!",
        text: "Ya conoces el flujo completo. Puedes repetir la guía cuando quieras.",
        placement: "bottom",
        advance: { kind: "manual" },
        final: true,
    },
];

/**
 * Reports of the problem the teacher picked in the examples flow. A problem that is not in the
 * summary (or none picked yet) falls back to the original showcase, `recorrido`.
 */
export function exampleCases(context: TourContext): Partial<Record<ExampleCase, number>> | null {
    const summary = context.examples;
    if (!summary) return null;
    const picked = summary.problemas.find((problem) => problem.problema_id === context.problemId);
    return picked?.casos ?? summary.recorrido.casos;
}

/** False when the step needs a case the picked problem does not have (it is skipped). */
export function stepApplies(step: TourStep, context: TourContext): boolean {
    if (!step.requiresCase) return true;
    const cases = exampleCases(context);
    return cases === null || cases[step.requiresCase] !== undefined;
}

/** Route of the example report for one case, or null when the summary is not loaded. */
function exampleReport(caso: ExampleCase): (context: TourContext) => string | null {
    return (context) => {
        const id = exampleCases(context)?.[caso];
        return id === undefined ? null : `/reporte/${id}`;
    };
}

const LIBRARY_ROUTE = () => "/biblioteca";

/** A report is fetched after its step starts, so its targets may take a while to appear. */
const REPORT_GRACE_MS = 8000;

/**
 * "Ver ejemplos": walks the preloaded example group. It has its own ending (the reports
 * are already analysed) and only describes what each metric measures.
 */
const EXAMPLE_STEPS: TourStep[] = [
    {
        id: "ex-library",
        target: "example-problems",
        title: "Tu grupo Ejemplo",
        text: "Elige el problema que más te interese.",
        placement: "bottom",
        advance: { kind: "pick" },
        // The library may still be reloading right after the group was created.
        graceMs: 8000,
        enterRoute: LIBRARY_ROUTE,
        showGroup: true,
    },
    {
        id: "ex-problem-submissions",
        target: "problem-submissions",
        title: "Sus entregas",
        text: "Estas son sus entregas con su similitud con la referencia.",
        placement: "top",
        advance: { kind: "manual" },
        graceMs: 4000,
        scopedToProblem: true,
        expandProblem: true,
        recoverTo: "ex-library",
    },
    {
        id: "ex-identical-semantic",
        target: "metric-semantic",
        title: "Entrega idéntica",
        text: "La similitud semántica compara la lógica: aquí es muy alta.",
        placement: "bottom",
        advance: { kind: "manual" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("identical"),
        reportView: "summary",
        recoverTo: "ex-library",
    },
    {
        id: "ex-identical-literal-extra",
        target: "metric-literal",
        title: "Dato extra",
        text: "Como dato extra, la coincidencia literal mide el texto compartido.",
        placement: "top",
        advance: { kind: "manual" },
        reportView: "summary",
        recoverTo: "ex-identical-semantic",
    },
    {
        id: "ex-code-open",
        target: "view-code",
        title: "Compara el código",
        text: "Pulsa «Ver código para comparar» para ver ambos programas.",
        placement: "bottom",
        advance: { kind: "click" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("identical"),
        reportView: "summary",
        recoverTo: "ex-identical-semantic",
    },
    {
        id: "ex-code-panes",
        target: "code-panes",
        title: "Entrega y referencia",
        text: "La entrega y la referencia se muestran juntas; los títulos indican cuál es cuál.",
        placement: "top",
        advance: { kind: "manual" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("identical"),
        reportView: "code",
        recoverTo: "ex-code-open",
    },
    {
        id: "ex-code-comment",
        target: "add-comment",
        title: "Deja un comentario",
        text: "Pulsa «+» junto a una línea para dejar un comentario de revisión.",
        placement: "right",
        advance: { kind: "manual" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("identical"),
        reportView: "code",
        recoverTo: "ex-code-open",
    },
    {
        id: "ex-similar-semantic",
        target: "metric-semantic",
        title: "Mismo problema, otra solución",
        text: "La lógica sigue parecida a la referencia, pero con un valor menor.",
        placement: "bottom",
        advance: { kind: "manual" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("similar"),
        reportView: "summary",
        recoverTo: "ex-library",
    },
    {
        id: "ex-similar-code",
        target: "code-panes",
        title: "Así se ve su código",
        text: "Mismo objetivo, otra forma de escribirlo: compara ambos programas.",
        placement: "top",
        advance: { kind: "manual" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("similar"),
        reportView: "code",
        recoverTo: "ex-similar-semantic",
    },
    {
        id: "ex-different-semantic",
        target: "metric-semantic",
        title: "Código de otro problema",
        text: "La lógica se parece aún menos a la de la referencia.",
        placement: "bottom",
        advance: { kind: "manual" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("different"),
        reportView: "summary",
        recoverTo: "ex-library",
    },
    {
        id: "ex-different-code",
        target: "code-panes",
        title: "Programas distintos",
        text: "Cada lado resuelve algo diferente: compara ambos programas.",
        placement: "top",
        advance: { kind: "manual" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("different"),
        reportView: "code",
        recoverTo: "ex-different-semantic",
    },
    {
        id: "ex-ai-style",
        target: "metric-style",
        title: "Estilo del código",
        text: "Mide qué tanto se parece la escritura a código generado por IA.",
        placement: "bottom",
        advance: { kind: "manual" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("ai"),
        reportView: "summary",
        requiresCase: "ai",
        recoverTo: "ex-library",
    },
    {
        id: "ex-done",
        title: "¡Eso es todo!",
        text: "Estos ejemplos se eligieron porque muestran bien cada caso; con otros códigos los resultados pueden variar. La decisión siempre es del docente. Puedes restaurar el grupo desde «Ver ejemplos».",
        placement: "bottom",
        advance: { kind: "manual" },
        enterRoute: LIBRARY_ROUTE,
        final: true,
    },
];

/** Flows that end with the shared "compare a submission and read the report" tail. */
const FLOW_HEADS: Record<Exclude<TourFlow, "examples">, TourStep[]> = {
    own: OWN_EXERCISE_STEPS,
    library: LIBRARY_STEPS,
};

export const TOUR_FLOWS: { flow: TourFlow; title: string; description: string }[] = [
    {
        flow: "own",
        title: "Subir mi propio ejercicio",
        description: "Registra tu solución y analiza una entrega.",
    },
    {
        flow: "library",
        title: "Usar un ejercicio de la biblioteca",
        description: "Elige uno precargado y analiza una entrega.",
    },
    {
        flow: "examples",
        title: "Ver ejemplos",
        description: "Recorre un grupo ya analizado: entrega idéntica, similar, distinta y de IA.",
    },
];

export function getSteps(flow: TourFlow): TourStep[] {
    if (flow === "examples") return EXAMPLE_STEPS;
    return [...FLOW_HEADS[flow], ...SHARED_TAIL];
}

/** The sibling of the two exercise flows; the examples flow has no sibling (it reopens the chooser). */
export function otherFlow(flow: Exclude<TourFlow, "examples">): Exclude<TourFlow, "examples"> {
    return flow === "own" ? "library" : "own";
}
