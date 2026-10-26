import React, { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

export type ModalMaxWidth = "sm" | "md" | "lg" | "xl" | "2xl" | "4xl" | "full";

export interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title?: React.ReactNode;
    description?: React.ReactNode;
    maxWidth?: ModalMaxWidth;
    fixedHeight?: string;
    children: React.ReactNode;
    footer?: React.ReactNode;
    closeOnBackdropClick?: boolean;
    closeOnEsc?: boolean;
    showCloseButton?: boolean;
    className?: string;
    bodyClassName?: string;
    containerClassName?: string;
    role?: "dialog" | "alertdialog";
    ariaLabelledBy?: string;
    ariaDescribedBy?: string;
}

const modalDimensions: Record<ModalMaxWidth, { width: string; height: string }> = {
    sm: { width: "max-w-sm", height: "h-[420px] max-h-[85vh]" },
    md: { width: "max-w-md", height: "h-[520px] max-h-[85vh]" },
    lg: { width: "max-w-lg", height: "h-[600px] max-h-[85vh]" },
    xl: { width: "max-w-xl", height: "h-[680px] max-h-[85vh]" },
    "2xl": { width: "max-w-2xl", height: "h-[720px] max-h-[86vh]" },
    "4xl": { width: "max-w-4xl", height: "h-[760px] max-h-[88vh]" },
    full: { width: "max-w-[95vw] lg:max-w-7xl", height: "h-[840px] max-h-[90vh]" },
};

/**
 * Accessible Modal component adhering to WCAG 2.1 AA dialog guidelines.
 * Uses createPortal into document.body, locks scroll, and supports smooth fluid animations.
 */
export function Modal({
    isOpen,
    onClose,
    title,
    description,
    maxWidth = "lg",
    fixedHeight,
    children,
    footer,
    closeOnBackdropClick = true,
    closeOnEsc = true,
    showCloseButton = true,
    className = "",
    bodyClassName = "",
    containerClassName = "",
    role = "dialog",
    ariaLabelledBy,
    ariaDescribedBy,
}: ModalProps) {
    const id = useId();
    const defaultTitleId = title ? `modal-title-${id}` : undefined;
    const defaultDescId = description ? `modal-desc-${id}` : undefined;
    const titleId = ariaLabelledBy ?? defaultTitleId;
    const descId = ariaDescribedBy ?? defaultDescId;
    const dialogRef = useRef<HTMLDivElement>(null);

    const [shouldRender, setShouldRender] = useState(isOpen);
    const [isVisible, setIsVisible] = useState(false);

    // Two-phase render lifecycle for smooth enter/exit animations
    useEffect(() => {
        let timer: ReturnType<typeof setTimeout>;

        if (isOpen) {
            setShouldRender(true);
            timer = setTimeout(() => {
                setIsVisible(true);
            }, 16);
        } else {
            setIsVisible(false);
            timer = setTimeout(() => {
                setShouldRender(false);
            }, 260);
        }

        return () => clearTimeout(timer);
    }, [isOpen]);

    // Lock document.body scroll while modal is open
    useEffect(() => {
        if (!isOpen || typeof document === "undefined") return;

        const originalOverflow = document.body.style.overflow;
        const originalPaddingRight = document.body.style.paddingRight;
        const scrollBarWidth = window.innerWidth - document.documentElement.clientWidth;

        document.body.style.overflow = "hidden";
        if (scrollBarWidth > 0) {
            document.body.style.paddingRight = `${scrollBarWidth}px`;
        }

        return () => {
            document.body.style.overflow = originalOverflow;
            document.body.style.paddingRight = originalPaddingRight;
        };
    }, [isOpen]);

    // Escape key listener
    useEffect(() => {
        if (!isOpen || !closeOnEsc || typeof window === "undefined") return;

        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                event.stopPropagation();
                onClose();
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, closeOnEsc, onClose]);

    if (!shouldRender || typeof document === "undefined") {
        return null;
    }

    const modalContent = (
        <div
            className={`fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 overflow-y-auto ${containerClassName}`}
        >
            {/* Backdrop */}
            <div
                className={`fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-300 ease-out ${
                    isVisible ? "opacity-100" : "opacity-0"
                }`}
                onClick={closeOnBackdropClick ? onClose : undefined}
                aria-hidden="true"
            />

            {/* Dialog Container */}
            {(() => {
                const dim = modalDimensions[maxWidth] ?? modalDimensions.lg;
                const heightClass = fixedHeight ?? (role === "alertdialog" ? "h-auto max-h-[85vh]" : dim.height);

                return (
                    <div
                        ref={dialogRef}
                        role={role}
                        aria-modal="true"
                        aria-labelledby={titleId}
                        aria-describedby={descId}
                        className={`relative w-full ${dim.width} ${heightClass} bg-white dark:bg-[#151c2e] border border-slate-200 dark:border-[#2b3346]/60 rounded-3xl shadow-2xl shadow-black/30 dark:shadow-black/70 overflow-hidden z-10 transition-all duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] transform flex flex-col my-auto ${
                            isVisible
                                ? "opacity-100 scale-100 translate-y-0"
                                : "opacity-0 scale-95 translate-y-3"
                        } ${className}`}
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Header */}
                        {(title || showCloseButton) && (
                            <div className="flex items-center justify-between px-6 py-5 sm:px-8 sm:py-6 border-b border-slate-200 dark:border-[#2b3346]/40 shrink-0">
                                <div className="min-w-0 pr-4">
                                    {title && (
                                        <h2
                                            id={titleId}
                                            className="text-xl font-display font-bold text-slate-900 dark:text-white"
                                        >
                                            {title}
                                        </h2>
                                    )}
                                    {description && (
                                        <p
                                            id={descId}
                                            className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1"
                                        >
                                            {description}
                                        </p>
                                    )}
                                </div>
                                {showCloseButton && (
                                    <button
                                        type="button"
                                        onClick={onClose}
                                        aria-label="Cerrar modal"
                                        className="p-1.5 text-slate-400 hover:text-slate-700 dark:text-slate-500 dark:hover:text-white rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 active:scale-95 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue shrink-0"
                                    >
                                        <X size={20} aria-hidden="true" />
                                    </button>
                                )}
                            </div>
                        )}

                        {/* Body Content */}
                        <div className={`p-6 sm:p-8 space-y-6 overflow-y-auto flex-1 ${bodyClassName}`}>
                            {children}
                        </div>

                        {/* Footer */}
                        {footer && (
                            <div className="px-6 py-4 sm:px-8 sm:py-5 border-t border-slate-200 dark:border-[#2b3346]/40 bg-slate-50 dark:bg-black/20 shrink-0">
                                {footer}
                            </div>
                        )}
                    </div>
                );
            })()}
        </div>
    );

    return createPortal(modalContent, document.body);
}
