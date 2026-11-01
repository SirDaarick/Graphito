/**
 * @file focusTrap.ts
 * @description Dialog focus management: move focus in when a dialog opens, keep Tab inside it
 * and give focus back to the control that opened it. The index logic is pure so it can be tested.
 */
import { useEffect, type RefObject } from "react";

const FOCUSABLE =
    'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Index to focus after Tab (or Shift+Tab) from `current` among `count` controls; wraps at both ends. */
export function nextFocusIndex(count: number, current: number, backwards: boolean): number {
    if (count <= 0) return -1;
    if (current < 0) return backwards ? count - 1 : 0;
    return backwards ? (current - 1 + count) % count : (current + 1) % count;
}

function isVisible(el: HTMLElement): boolean {
    return el.getClientRects().length > 0;
}

function focusableIn(container: HTMLElement): HTMLElement[] {
    return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(isVisible);
}

/**
 * While `active`, focus starts on `[data-autofocus]`, else on the first form field, else on the
 * dialog itself; Tab cycles inside `containerRef`; on close focus returns to the opener.
 */
export function useDialogFocus(containerRef: RefObject<HTMLElement | null>, active: boolean): void {
    useEffect(() => {
        const container = containerRef.current;
        if (!active || !container) return;

        const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;

        if (!container.hasAttribute("tabindex")) container.setAttribute("tabindex", "-1");
        const initial =
            container.querySelector<HTMLElement>("[data-autofocus]") ??
            container.querySelector<HTMLElement>("input:not([disabled]):not([type='hidden']), select:not([disabled]), textarea:not([disabled])") ??
            container;
        initial.focus({ preventScroll: true });

        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key !== "Tab") return;
            const items = focusableIn(container);
            if (items.length === 0) {
                event.preventDefault();
                container.focus();
                return;
            }
            const current = items.indexOf(document.activeElement as HTMLElement);
            const next = nextFocusIndex(items.length, current, event.shiftKey);
            const leaving = event.shiftKey ? current <= 0 : current === items.length - 1;
            // Only take over at the edges (or when focus is outside the list); let the browser move inside.
            if (leaving || current < 0) {
                event.preventDefault();
                items[next].focus();
            }
        };
        container.addEventListener("keydown", onKeyDown);

        return () => {
            container.removeEventListener("keydown", onKeyDown);
            if (opener && opener.isConnected) opener.focus({ preventScroll: true });
        };
    }, [containerRef, active]);
}
