/**
 * @file router.ts
 * @description Lightweight SPA router utilities and reactive hooks using HTML5 History API.
 */
import { useSyncExternalStore, useMemo } from "react";
import { api } from "./api";

export interface NavigateOptions {
    replace?: boolean;
    state?: any;
}

export interface RouteMatch {
    isMatch: boolean;
    params: Record<string, string>;
}

export const ROUTE_CHANGE_EVENT = "graphito:routechange";

/**
 * Normalizes a path string:
 * - strips queries and hash fragments
 * - guarantees a leading slash
 * - strips redundant trailing slashes (except root "/")
 */
export function normalizePath(path: string): string {
    if (!path) return "/";
    const clean = path.split(/[?#]/)[0] || "/";
    const withLeading = clean.startsWith("/") ? clean : `/${clean}`;
    if (withLeading.length > 1 && withLeading.endsWith("/")) {
        return withLeading.replace(/\/+$/, "");
    }
    return withLeading;
}

/**
 * Pure route pattern matcher. Supports literal segments and param tokens like `:id`.
 */
export function matchRoute(pattern: string, path: string): RouteMatch {
    const cleanPath = normalizePath(path);
    const cleanPattern = normalizePath(pattern);

    if (cleanPattern === cleanPath) {
        return { isMatch: true, params: {} };
    }

    const patternSegs = cleanPattern.split("/").filter(Boolean);
    const pathSegs = cleanPath.split("/").filter(Boolean);

    if (patternSegs.length !== pathSegs.length) {
        return { isMatch: false, params: {} };
    }

    const params: Record<string, string> = {};

    for (let i = 0; i < patternSegs.length; i++) {
        const pSeg = patternSegs[i];
        const aSeg = pathSegs[i];

        if (pSeg.startsWith(":")) {
            const paramName = pSeg.slice(1);
            params[paramName] = decodeURIComponent(aSeg);
        } else if (pSeg !== aSeg) {
            return { isMatch: false, params: {} };
        }
    }

    return { isMatch: true, params };
}

/**
 * Navigates to a specific path using pushState or replaceState.
 * Dispatches a custom route change event so all hook consumers update reactively.
 */
export function navigate(path: string, options?: NavigateOptions): void {
    if (typeof window === "undefined") return;

    const targetPath = normalizePath(path);

    if (options?.replace) {
        window.history.replaceState(options?.state ?? null, "", targetPath);
    } else {
        window.history.pushState(options?.state ?? null, "", targetPath);
    }

    window.dispatchEvent(
        new CustomEvent(ROUTE_CHANGE_EVENT, {
            detail: { path: targetPath, state: options?.state },
        })
    );
}

/**
 * Returns current history state if in browser environment, otherwise null.
 */
export function getHistoryState<T = any>(): T | null {
    if (typeof window === "undefined") return null;
    return window.history.state as T;
}

/**
 * Subscribes a listener to browser navigation (popstate) and programmatic SPA navigation events.
 * Returns an unmount / cleanup function.
 */
export function subscribeToRoute(callback: () => void): () => void {
    if (typeof window === "undefined") return () => {};

    window.addEventListener("popstate", callback);
    window.addEventListener(ROUTE_CHANGE_EVENT, callback);

    return () => {
        window.removeEventListener("popstate", callback);
        window.removeEventListener(ROUTE_CHANGE_EVENT, callback);
    };
}

function getPathSnapshot(): string {
    if (typeof window === "undefined") return "/";
    return normalizePath(window.location.pathname);
}

/**
 * Reactive hook returning the current pathname.
 * Uses useSyncExternalStore for zero tearing and clean teardown.
 */
export function usePath(): string {
    return useSyncExternalStore(subscribeToRoute, getPathSnapshot, () => "/");
}

/**
 * Reactive hook returning whether the current path matches the given pattern and extracted params.
 */
export function useRouteMatch(pattern: string): RouteMatch {
    const currentPath = usePath();
    return useMemo(() => matchRoute(pattern, currentPath), [pattern, currentPath]);
}

/**
 * Parses current path, defaulting to "/biblioteca" (or "/login" if unauthenticated).
 */
export function getInitialRoute(isAuthenticated?: boolean): string {
    const isAuth = isAuthenticated !== undefined
        ? isAuthenticated
        : (typeof window !== "undefined" ? api.auth.isAuthenticated() : false);

    if (typeof window === "undefined") {
        return isAuth ? "/biblioteca" : "/login";
    }

    const currentPath = normalizePath(window.location.pathname);

    // Auth routes
    if (currentPath === "/login" || currentPath === "/register") {
        return isAuth ? "/biblioteca" : currentPath;
    }

    // Unauthenticated access redirects to login
    if (!isAuth) {
        return "/login";
    }

    // Authenticated access at root
    if (currentPath === "/") {
        return "/biblioteca";
    }

    // Known authorized routes or deep links
    if (
        currentPath === "/biblioteca" ||
        currentPath === "/catalogo" ||
        matchRoute("/reporte/:id", currentPath).isMatch
    ) {
        return currentPath;
    }

    // Fallback for unknown routes
    return "/biblioteca";
}
