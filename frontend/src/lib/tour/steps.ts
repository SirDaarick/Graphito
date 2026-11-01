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

/** Route of the example report for one case, or null when the summary is not loaded. */
function exampleReport(caso: ExampleCase): (context: TourContext) => string | null {
    return (context) => {
        const id = context.examples?.recorrido.casos[caso];
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
        target: "problem-card",
        title: "Tu grupo Ejemplo",
        text: "Trae un problema ya analizado con cuatro entregas de muestra.",
        placement: "bottom",
        advance: { kind: "manual" },
        scopedToProblem: true,
        // The library may still be reloading right after the group was created.
        graceMs: 8000,
        enterRoute: LIBRARY_ROUTE,
        showGroup: true,
    },
    {
        id: "ex-identical-literal",
        target: "metric-literal",
        title: "Entrega idéntica",
        text: "La coincidencia literal mide el texto compartido: aquí es muy alta.",
        placement: "top",
        advance: { kind: "manual" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("identical"),
        reportView: "summary",
        recoverTo: "ex-library",
    },
    {
        id: "ex-identical-semantic",
        target: "metric-semantic",
        title: "Similitud semántica",
        text: "Compara la lógica con la referencia, aunque cambien los nombres.",
        placement: "bottom",
        advance: { kind: "manual" },
        recoverTo: "ex-identical-literal",
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
        recoverTo: "ex-identical-literal",
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
        id: "ex-similar-literal",
        target: "metric-literal",
        title: "Mismo problema, otra solución",
        text: "Escrita por separado, comparte menos texto con la referencia.",
        placement: "top",
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
        text: "Mismo objetivo, otra forma de escribirlo: se marcan las líneas distintas.",
        placement: "top",
        advance: { kind: "manual" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("similar"),
        reportView: "code",
        recoverTo: "ex-similar-literal",
    },
    {
        id: "ex-different-literal",
        target: "metric-literal",
        title: "Código de otro problema",
        text: "Al ser de otro problema, comparte aún menos texto con la referencia.",
        placement: "top",
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
        text: "Cada lado resuelve algo diferente; se marcan las líneas que difieren.",
        placement: "top",
        advance: { kind: "manual" },
        graceMs: REPORT_GRACE_MS,
        enterRoute: exampleReport("different"),
        reportView: "code",
        recoverTo: "ex-different-literal",
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
