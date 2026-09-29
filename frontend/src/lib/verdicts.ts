/**
 * @file verdicts.ts
 * @description Gestión reactiva y persistencia local de veredictos emitidos por el docente.
 * Permite sincronizar en tiempo real el estado de una entrega ("CONFORME" o "DUDA")
 * entre el modal de reporte/diff y la lista de tareas/referencias (ReferenceCard)
 * mediante CustomEvents de ventana y localStorage.
 */

export type VerdictType = "CONFORME" | "DUDA";

const STORAGE_KEY = "graphito_submission_verdicts";

/**
 * Obtiene el mapa completo de veredictos guardados en el almacenamiento local.
 * @returns {Record<string, VerdictType>} Diccionario mapeando comparisonId -> VerdictType.
 */
export function getSavedVerdicts(): Record<string, VerdictType> {
    try {
        const item = localStorage.getItem(STORAGE_KEY);
        return item ? JSON.parse(item) : {};
    } catch {
        return {};
    }
}

/**
 * Persiste el veredicto del docente para una entrega específica y despacha
 * un evento global 'graphito_verdict_updated' para reactividad sin re-renderizado forzado.
 * @param comparisonId Identificador de la comparación o reporte.
 * @param verdict Veredicto ("CONFORME" | "DUDA").
 */
export function saveVerdict(comparisonId: string | number, verdict: VerdictType): void {
    try {
        const verdicts = getSavedVerdicts();
        verdicts[String(comparisonId)] = verdict;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(verdicts));
        window.dispatchEvent(
            new CustomEvent("graphito_verdict_updated", {
                detail: { comparisonId: String(comparisonId), verdict },
            })
        );
    } catch (e) {
        console.error("Error al persistir veredicto docente:", e);
    }
}

/**
 * Consulta el veredicto previamente emitido para una comparación dada.
 * @param comparisonId Identificador de la comparación.
 * @returns {VerdictType | null} El veredicto almacenado o null si no se ha emitido uno.
 */
export function getVerdict(comparisonId: string | number): VerdictType | null {
    const verdicts = getSavedVerdicts();
    return verdicts[String(comparisonId)] || null;
}

