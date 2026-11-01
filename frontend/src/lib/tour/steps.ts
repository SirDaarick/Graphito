import type { TourFlow, TourStep } from "./types";

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

const FLOW_HEADS: Record<TourFlow, TourStep[]> = {
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
];

export function getSteps(flow: TourFlow): TourStep[] {
    return [...FLOW_HEADS[flow], ...SHARED_TAIL];
}

export function otherFlow(flow: TourFlow): TourFlow {
    return flow === "own" ? "library" : "own";
}
