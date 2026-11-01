import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { HelpCircle, X } from "lucide-react";

interface InfoPopoverProps {
    /** Accessible name of the "?" button, e.g. "Cómo se calcula la similitud semántica". */
    label: string;
    /** Heading shown inside the popover. */
    title: string;
    children: ReactNode;
    /** Positioning classes for the wrapper; it must establish a positioning context ("relative" or "absolute ..."). */
    className?: string;
}

/**
 * A "?" button that opens a small explanation panel.
 * Keyboard: Enter/Space toggles, Escape closes (and does not close the surrounding modal),
 * focus moves into the panel on open and returns to the button on close.
 */
export function InfoPopover({ label, title, children, className = "relative" }: InfoPopoverProps) {
    const [open, setOpen] = useState(false);
    const rootRef = useRef<HTMLSpanElement>(null);
    const buttonRef = useRef<HTMLButtonElement>(null);
    const panelRef = useRef<HTMLDivElement>(null);
    const panelId = useId();
    const titleId = useId();

    // The panel is portaled into the surrounding dialog (or body) so no ancestor overflow can clip it,
    // and placed next to the button, clamped to the container's bounds.
    const [container, setContainer] = useState<HTMLElement | null>(null);
    const [pos, setPos] = useState<{ top: number; left: number; maxHeight: number } | null>(null);

    useLayoutEffect(() => {
        if (!open) {
            setPos(null);
            return;
        }
        const host = (buttonRef.current?.closest('[role="dialog"]') as HTMLElement | null) ?? document.body;
        setContainer(host);

        const place = () => {
            const btn = buttonRef.current;
            const panel = panelRef.current;
            if (!btn || !panel) return;
            const margin = 12;
            const isBody = host === document.body;
            const box = isBody
                ? { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight }
                : host.getBoundingClientRect();
            const b = btn.getBoundingClientRect();
            const width = panel.offsetWidth;
            const maxHeight = Math.max(120, box.height - margin * 2);
            const height = Math.min(panel.scrollHeight, maxHeight);

            let left = b.right - box.left - width;
            left = Math.min(Math.max(margin, left), box.width - width - margin);

            let top = b.bottom - box.top + 4;
            if (top + height > box.height - margin) top = b.top - box.top - height - 4;
            top = Math.min(Math.max(margin, top), box.height - height - margin);

            setPos({ top, left, maxHeight });
        };

        place();
        window.addEventListener("resize", place);
        window.addEventListener("scroll", place, true);
        return () => {
            window.removeEventListener("resize", place);
            window.removeEventListener("scroll", place, true);
        };
    }, [open, container]);

    useEffect(() => {
        if (!open) return;
        panelRef.current?.focus({ preventScroll: true });

        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key !== "Escape") return;
            e.preventDefault();
            e.stopPropagation();
            setOpen(false);
            buttonRef.current?.focus();
        };
        const onPointerDown = (e: PointerEvent) => {
            const target = e.target as Node;
            if (rootRef.current?.contains(target) || panelRef.current?.contains(target)) return;
            setOpen(false);
        };

        // Capture phase so Escape closes only this panel, not the modal behind it.
        document.addEventListener("keydown", onKeyDown, true);
        document.addEventListener("pointerdown", onPointerDown);
        return () => {
            document.removeEventListener("keydown", onKeyDown, true);
            document.removeEventListener("pointerdown", onPointerDown);
        };
    }, [open]);

    return (
        <span ref={rootRef} className={`inline-flex ${className}`}>
            <button
                ref={buttonRef}
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-label={label}
                aria-expanded={open}
                aria-controls={open ? panelId : undefined}
                className="flex h-9 w-9 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-slate-200/70 hover:text-graphito-blue focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/60 dark:text-slate-500 dark:hover:bg-slate-700/60 dark:hover:text-graphito-blue"
            >
                <HelpCircle size={18} aria-hidden="true" />
            </button>

            {open && container && createPortal(
                <div
                    ref={panelRef}
                    id={panelId}
                    role="dialog"
                    aria-labelledby={titleId}
                    tabIndex={-1}
                    style={{
                        position: container === document.body ? "fixed" : "absolute",
                        top: pos?.top ?? 0,
                        left: pos?.left ?? 0,
                        maxHeight: pos?.maxHeight,
                        visibility: pos ? "visible" : "hidden",
                    }}
                    className="z-[300] w-[min(22rem,calc(100vw-4rem))] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-4 text-left text-xs leading-relaxed text-slate-700 shadow-2xl focus:outline-none dark:border-[#2b3346] dark:bg-[#141b2c] dark:text-slate-300"
                >
                    <div className="mb-2 flex items-start justify-between gap-2">
                        <h5 id={titleId} className="text-sm font-bold text-slate-900 dark:text-white">
                            {title}
                        </h5>
                        <button
                            type="button"
                            onClick={() => {
                                setOpen(false);
                                buttonRef.current?.focus();
                            }}
                            aria-label="Cerrar explicación"
                            className="-mr-1 -mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-400 hover:bg-slate-200/70 hover:text-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue/60 dark:hover:bg-slate-700/60 dark:hover:text-white"
                        >
                            <X size={15} aria-hidden="true" />
                        </button>
                    </div>
                    <div className="space-y-3">{children}</div>
                </div>,
                container
            )}
        </span>
    );
}

/** A titled paragraph block used inside an InfoPopover. */
export function InfoSection({ heading, children }: { heading: string; children: ReactNode }) {
    return (
        <section>
            <h6 className="mb-0.5 text-[11px] font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">{heading}</h6>
            <div>{children}</div>
        </section>
    );
}
