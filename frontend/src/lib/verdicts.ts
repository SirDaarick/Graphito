export type VerdictType = "CONFORME" | "DUDA";

const STORAGE_KEY = "graphito_submission_verdicts";

export function getSavedVerdicts(): Record<string, VerdictType> {
    try {
        const item = localStorage.getItem(STORAGE_KEY);
        return item ? JSON.parse(item) : {};
    } catch {
        return {};
    }
}

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

export function getVerdict(comparisonId: string | number): VerdictType | null {
    const verdicts = getSavedVerdicts();
    return verdicts[String(comparisonId)] || null;
}
