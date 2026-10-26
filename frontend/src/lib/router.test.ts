/**
 * @file router.test.ts
 * @description Unit tests for router utilities, pattern matching, navigation, and history events.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
    normalizePath,
    matchRoute,
    navigate,
    getHistoryState,
    subscribeToRoute,
    getInitialRoute,
    ROUTE_CHANGE_EVENT,
} from "./router";

describe("normalizePath", () => {
    it("handles empty or falsy paths", () => {
        expect(normalizePath("")).toBe("/");
        expect(normalizePath("/")).toBe("/");
    });

    it("ensures a leading slash", () => {
        expect(normalizePath("biblioteca")).toBe("/biblioteca");
        expect(normalizePath("catalogo")).toBe("/catalogo");
    });

    it("strips trailing slashes while preserving root", () => {
        expect(normalizePath("/biblioteca/")).toBe("/biblioteca");
        expect(normalizePath("/reporte/101///")).toBe("/reporte/101");
        expect(normalizePath("/")).toBe("/");
    });

    it("strips query parameters and hash fragments", () => {
        expect(normalizePath("/reporte/101?view=diff")).toBe("/reporte/101");
        expect(normalizePath("/catalogo#search")).toBe("/catalogo");
        expect(normalizePath("/reporte/101?view=diff#anchor")).toBe("/reporte/101");
    });
});

describe("matchRoute", () => {
    it("matches exact static routes", () => {
        const match = matchRoute("/biblioteca", "/biblioteca");
        expect(match.isMatch).toBe(true);
        expect(match.params).toEqual({});
    });

    it("matches root route", () => {
        const match = matchRoute("/", "/");
        expect(match.isMatch).toBe(true);
        expect(match.params).toEqual({});
    });

    it("returns false for non-matching static routes", () => {
        const match = matchRoute("/biblioteca", "/catalogo");
        expect(match.isMatch).toBe(false);
        expect(match.params).toEqual({});
    });

    it("extracts dynamic parameter tokens", () => {
        const match = matchRoute("/reporte/:id", "/reporte/101");
        expect(match.isMatch).toBe(true);
        expect(match.params).toEqual({ id: "101" });
    });

    it("extracts and decodes URI encoded parameters", () => {
        const match = matchRoute("/cursos/:code", "/cursos/EST-101%20A");
        expect(match.isMatch).toBe(true);
        expect(match.params).toEqual({ code: "EST-101 A" });
    });

    it("rejects path if segment count does not match", () => {
        expect(matchRoute("/reporte/:id", "/reporte").isMatch).toBe(false);
        expect(matchRoute("/reporte/:id", "/reporte/101/details").isMatch).toBe(false);
    });

    it("tolerates trailing slashes and query strings on both pattern and path", () => {
        const match = matchRoute("/reporte/:id/", "/reporte/42?active=1#sec");
        expect(match.isMatch).toBe(true);
        expect(match.params).toEqual({ id: "42" });
    });
});

describe("getInitialRoute", () => {
    const originalWindow = globalThis.window;

    afterEach(() => {
        globalThis.window = originalWindow;
    });

    it("returns /login when unauthenticated attempting to access protected routes", () => {
        (globalThis as any).window = {
            location: { pathname: "/biblioteca" },
        };
        expect(getInitialRoute(false)).toBe("/login");

        (globalThis as any).window = {
            location: { pathname: "/catalogo" },
        };
        expect(getInitialRoute(false)).toBe("/login");

        (globalThis as any).window = {
            location: { pathname: "/reporte/101" },
        };
        expect(getInitialRoute(false)).toBe("/login");
    });

    it("allows /login and /register when unauthenticated", () => {
        (globalThis as any).window = {
            location: { pathname: "/login" },
        };
        expect(getInitialRoute(false)).toBe("/login");

        (globalThis as any).window = {
            location: { pathname: "/register" },
        };
        expect(getInitialRoute(false)).toBe("/register");
    });

    it("redirects authenticated user from /login or /register to /biblioteca", () => {
        (globalThis as any).window = {
            location: { pathname: "/login" },
        };
        expect(getInitialRoute(true)).toBe("/biblioteca");

        (globalThis as any).window = {
            location: { pathname: "/register" },
        };
        expect(getInitialRoute(true)).toBe("/biblioteca");
    });

    it("preserves recognized routes for authenticated user", () => {
        (globalThis as any).window = {
            location: { pathname: "/catalogo" },
        };
        expect(getInitialRoute(true)).toBe("/catalogo");

        (globalThis as any).window = {
            location: { pathname: "/reporte/999" },
        };
        expect(getInitialRoute(true)).toBe("/reporte/999");
    });

    it("defaults root / to /biblioteca for authenticated user and /login for unauthenticated", () => {
        (globalThis as any).window = {
            location: { pathname: "/" },
        };
        expect(getInitialRoute(true)).toBe("/biblioteca");
        expect(getInitialRoute(false)).toBe("/login");
    });
});

describe("navigate, subscribeToRoute, and history events", () => {
    let mockListeners: Record<string, Set<EventListener>>;
    let mockState: any;
    let mockPathname: string;
    let pushStateMock: any;
    let replaceStateMock: any;
    const originalWindow = globalThis.window;
    const originalCustomEvent = globalThis.CustomEvent;

    beforeEach(() => {
        mockListeners = {
            popstate: new Set(),
            [ROUTE_CHANGE_EVENT]: new Set(),
        };
        mockState = null;
        mockPathname = "/biblioteca";

        pushStateMock = vi.fn((state: any, _title: string, url: string) => {
            mockState = state;
            mockPathname = url;
        });

        replaceStateMock = vi.fn((state: any, _title: string, url: string) => {
            mockState = state;
            mockPathname = url;
        });

        const mockWindow = {
            location: {
                get pathname() {
                    return mockPathname;
                },
                set pathname(val: string) {
                    mockPathname = val;
                },
            },
            history: {
                get state() {
                    return mockState;
                },
                pushState: pushStateMock,
                replaceState: replaceStateMock,
            },
            addEventListener: vi.fn((event: string, listener: EventListener) => {
                if (!mockListeners[event]) mockListeners[event] = new Set();
                mockListeners[event].add(listener);
            }),
            removeEventListener: vi.fn((event: string, listener: EventListener) => {
                mockListeners[event]?.delete(listener);
            }),
            dispatchEvent: vi.fn((event: Event) => {
                mockListeners[event.type]?.forEach((listener) => listener(event));
                return true;
            }),
        };

        (globalThis as any).window = mockWindow;
        (globalThis as any).CustomEvent = class MockCustomEvent {
            type: string;
            detail: any;
            constructor(type: string, init?: { detail: any }) {
                this.type = type;
                this.detail = init?.detail;
            }
        };
    });

    afterEach(() => {
        globalThis.window = originalWindow;
        globalThis.CustomEvent = originalCustomEvent;
    });

    it("navigate updates window history with pushState by default and dispatches event", () => {
        navigate("/catalogo", { state: { test: 123 } });

        expect(pushStateMock).toHaveBeenCalledWith({ test: 123 }, "", "/catalogo");
        expect(replaceStateMock).not.toHaveBeenCalled();
        expect(window.dispatchEvent).toHaveBeenCalled();
        expect(getHistoryState()).toEqual({ test: 123 });
    });

    it("navigate with replace: true calls replaceState", () => {
        navigate("/reporte/101", { replace: true, state: { modal: true } });

        expect(replaceStateMock).toHaveBeenCalledWith({ modal: true }, "", "/reporte/101");
        expect(pushStateMock).not.toHaveBeenCalled();
    });

    it("subscribeToRoute triggers callback on route change and popstate events", () => {
        const callback = vi.fn();
        const unsubscribe = subscribeToRoute(callback);

        // Simulate navigate
        navigate("/catalogo");
        expect(callback).toHaveBeenCalledTimes(1);

        // Simulate browser back / popstate
        window.dispatchEvent(new Event("popstate"));
        expect(callback).toHaveBeenCalledTimes(2);

        // Unsubscribe
        unsubscribe();
        navigate("/biblioteca");
        window.dispatchEvent(new Event("popstate"));
        expect(callback).toHaveBeenCalledTimes(2);
    });
});

describe("SSR safety", () => {
    const originalWindow = globalThis.window;

    beforeEach(() => {
        delete (globalThis as any).window;
    });

    afterEach(() => {
        globalThis.window = originalWindow;
    });

    it("does not throw when window is undefined", () => {
        expect(() => navigate("/biblioteca")).not.toThrow();
        expect(getHistoryState()).toBeNull();
        expect(getInitialRoute(false)).toBe("/login");
        expect(getInitialRoute(true)).toBe("/biblioteca");

        const unsub = subscribeToRoute(() => {});
        expect(() => unsub()).not.toThrow();
    });
});
