import { forwardRef, type CSSProperties } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, MousePointerClick, X, type LucideIcon } from "lucide-react";
import { Button } from "../ui/Button";
import type { TooltipPosition } from "../../lib/tour/geometry";
import type { TourPlacement, TourStep } from "../../lib/tour/types";

export type TooltipMode = "step" | "lost";

interface TourTooltipProps {
    step: TourStep;
    mode: TooltipMode;
    current: number;
    total: number;
    isFirst: boolean;
    filled: boolean;
    /** Anchored next to the target; omit for a card centered on screen. */
    position?: TooltipPosition;
    recoverLabel?: string;
    /** Label of the secondary button on the final card. */
    otherFlowLabel: string;
    onNext: () => void;
    onBack: () => void;
    onExit: () => void;
    onRecover: () => void;
    onOtherFlow: () => void;
}

/** Side of the card that carries the arrow, and the borders that draw its tip. */
const ARROW_BY_PLACEMENT: Record<TourPlacement, { side: "top" | "bottom" | "left" | "right"; borders: string }> = {
    bottom: { side: "top", borders: "border-t border-l" },
    top: { side: "bottom", borders: "border-b border-r" },
    right: { side: "left", borders: "border-b border-l" },
    left: { side: "right", borders: "border-t border-r" },
};

const ARROW_SIZE = 14;

/** Icon pointing from the card toward its target (the card sits on `placement` side of it). */
const POINTER_BY_PLACEMENT: Record<TourPlacement, { Icon: LucideIcon; className: string }> = {
    bottom: { Icon: ArrowUp, className: "tour-nudge-y" },
    top: { Icon: ArrowDown, className: "tour-nudge-y" },
    right: { Icon: ArrowLeft, className: "tour-nudge-x" },
    left: { Icon: ArrowRight, className: "tour-nudge-x" },
};

export const TourTooltip = forwardRef<HTMLDivElement, TourTooltipProps>(function TourTooltip(
    { step, mode, current, total, isFirst, filled, position, recoverLabel, otherFlowLabel, onNext, onBack, onExit, onRecover, onOtherFlow },
    ref
) {
    const isLost = mode === "lost";
    const arrow = position && !isLost ? ARROW_BY_PLACEMENT[position.placement] : null;

    const style: CSSProperties = position
        ? { top: position.top, left: position.left }
        : { top: "50%", left: "50%", transform: "translate(-50%, -50%)" };

    const arrowStyle: CSSProperties | undefined =
        arrow && position
            ? {
                  [arrow.side]: -ARROW_SIZE / 2,
                  ...(arrow.side === "top" || arrow.side === "bottom"
                      ? { left: position.arrowOffset - ARROW_SIZE / 2 }
                      : { top: position.arrowOffset - ARROW_SIZE / 2 }),
                  width: ARROW_SIZE,
                  height: ARROW_SIZE,
              }
            : undefined;

    const pointer = position && !isLost ? POINTER_BY_PLACEMENT[position.placement] : null;
    const advance = step.advance;
    const title = isLost ? "No encuentro este paso" : step.title;
    const text = isLost ? "Parece que cerraste la ventana. Puedes retomar donde ibas." : step.text;

    return (
        <div
            ref={ref}
            role="dialog"
            aria-live="polite"
            aria-label={title}
            style={style}
            className="fixed pointer-events-auto w-[320px] max-w-[calc(100vw-24px)]"
        >
            <div
                key={`${step.id}-${mode}`}
                className="tour-pop relative rounded-2xl border border-slate-200 dark:border-graphito-border bg-white dark:bg-graphito-card shadow-2xl shadow-black/30 p-4"
            >
                {arrowStyle && arrow && (
                    <span
                        aria-hidden="true"
                        style={arrowStyle}
                        className={`absolute rotate-45 bg-white dark:bg-graphito-card border-slate-200 dark:border-graphito-border ${arrow.borders}`}
                    />
                )}

                <div className="flex items-center justify-between gap-2 mb-2">
                    {isLost || step.final ? (
                        <span className="w-0" />
                    ) : (
                        <span className="text-[10px] font-black uppercase tracking-widest text-graphito-blue">
                            Paso {current} de {total}
                        </span>
                    )}
                    <button
                        type="button"
                        onClick={onExit}
                        aria-label="Salir de la guía"
                        className="-m-1 p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-graphito-surface focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue transition-colors"
                    >
                        <X size={16} />
                    </button>
                </div>

                <h3 className="font-display font-bold text-base text-slate-900 dark:text-white leading-snug">{title}</h3>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{text}</p>

                {!isLost && !step.final && (
                    <div className="mt-3 h-1 rounded-full bg-slate-200 dark:bg-graphito-surface overflow-hidden" aria-hidden="true">
                        <div
                            className="h-full rounded-full bg-button-grad transition-[width] duration-300"
                            style={{ width: `${(current / total) * 100}%` }}
                        />
                    </div>
                )}

                <div className="mt-4 flex items-center justify-between gap-2 min-h-[36px]">
                    {isLost ? (
                        <>
                            <Button variant="ghost" size="sm" onClick={onExit}>
                                Salir
                            </Button>
                            {recoverLabel && (
                                <Button variant="gradient" size="sm" onClick={onRecover}>
                                    {recoverLabel}
                                </Button>
                            )}
                        </>
                    ) : step.final ? (
                        <>
                            <Button variant="ghost" size="sm" onClick={onOtherFlow}>
                                {otherFlowLabel}
                            </Button>
                            <Button variant="gradient" size="sm" onClick={onNext}>
                                Finalizar
                            </Button>
                        </>
                    ) : (
                        <>
                            {isFirst ? <span /> : (
                                <Button variant="ghost" size="sm" onClick={onBack}>
                                    Atrás
                                </Button>
                            )}
                            {advance.kind === "filled" || advance.kind === "manual" ? (
                                <Button
                                    variant="gradient"
                                    size="sm"
                                    onClick={onNext}
                                    disabled={advance.kind === "filled" && !filled}
                                >
                                    {advance.kind === "filled" ? "Siguiente" : "Entendido"}
                                </Button>
                            ) : (
                                // Not a button: the user must act on the highlighted element, so the hint points at it.
                                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-graphito-blue">
                                    {pointer ? (
                                        <pointer.Icon size={14} aria-hidden="true" className={pointer.className} />
                                    ) : (
                                        <MousePointerClick size={14} aria-hidden="true" />
                                    )}
                                    Haz clic en el botón señalado
                                </span>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
});
