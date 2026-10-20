import { useEffect, useId, useRef, useState, type ReactNode } from "react";
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
            if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
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

            {open && (
                <div
                    ref={panelRef}
                    id={panelId}
                    role="dialog"
                    aria-labelledby={titleId}
                    tabIndex={-1}
                    className="absolute right-0 top-full z-40 mt-1 w-[min(22rem,calc(100vw-2.5rem))] max-h-[60vh] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-4 text-left text-xs leading-relaxed text-slate-700 shadow-2xl focus:outline-none dark:border-[#2b3346] dark:bg-[#141b2c] dark:text-slate-300"
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
                </div>
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
