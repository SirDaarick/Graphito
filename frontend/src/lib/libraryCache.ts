/**
 * In-memory copy of the last library load, so going back to the library (or reopening the app in the
 * same tab) shows it at once while a fresh copy loads. Dropped whenever the session changes.
 */
import type { ComparisonView } from "./dictamen";

const store = new Map<string, unknown>();

export const LIBRARY_CACHE_KEY = "library:active";

export const libraryCache = {
    get<T>(key: string): T | undefined {
        return store.get(key) as T | undefined;
    },
    set(key: string, value: unknown): void {
        store.set(key, value);
    },
    clear(): void {
        store.clear();
    },
};

/**
 * A report the library already loaded, with the other reports of its problem (for paging), or null.
 * Lets a direct link to a report (e.g. the guided tour opening one) skip the network round trips.
 */
export function findCachedReport(
    reportId: number
): { current: ComparisonView; list: ComparisonView[] } | null {
    const snapshot = libraryCache.get<{ references: { comparisons: ComparisonView[] }[] }>(LIBRARY_CACHE_KEY);
    for (const reference of snapshot?.references ?? []) {
        // Submissions still without a report carry a submission id (not numeric): they cannot be opened.
        const reports = reference.comparisons.filter((c) => /^\d+$/.test(String(c.id)));
        const current = reports.find((c) => String(c.id) === String(reportId));
        if (current) return { current, list: reports };
    }
    return null;
}
