import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Loader2 } from "lucide-react";
import { computeTooltipPosition } from "../../lib/tour/geometry";
import { currentStep, resolveTargetSelectors, routeAdvancesStep, stepEntryPath, stepProgress } from "../../lib/tour/machine";
import { requestReportView } from "../../lib/tour/reportView";
import { otherFlow } from "../../lib/tour/steps";
import type { Size } from "../../lib/tour/types";
import { matchRoute, navigate, normalizePath, subscribeToRoute } from "../../lib/router";
import { useTour } from "./TourContext";
import { TourTooltip } from "./TourTooltip";
import { useTourTarget } from "./useTourTarget";

const DIM = "rgba(15, 23, 42, 0.55)";
const WAITING_CHIP_MS = 500;
const DEFAULT_GRACE_MS = 2500;
const FALLBACK_GRACE_MS = 800;
const MOVE_TRANSITION_MS = 320;

function isFilled(element: HTMLElement | null): boolean {
    if (!element) return false;
    const fields = element.matches("input, textarea")
        ? [element as HTMLInputElement]
        : Array.from(element.querySelectorAll<HTMLInputElement>("textarea, input:not([type=file]):not([type=checkbox])"));
    return fields.some((field) => field.value.trim().length > 0);
}

export function TourOverlay() {
    const { state, next, back, goTo, exit, choose, open } = useTour();
    const step = currentStep(state);
    const { current, total } = stepProgress(state);
    const problemId = state.context.problemId;
    const entryPath = step ? stepEntryPath(step, state.context) : null;
    const reportView = step?.reportView;

    const selectors = useMemo(() => (step ? resolveTargetSelectors(step, { problemId }) : []), [step, problemId]);
    const target = useTourTarget(selectors, step?.id ?? null);

    const [filled, setFilled] = useState(false);
    const [phase, setPhase] = useState<"ok" | "waiting" | "lost">("ok");
    const [moving, setMoving] = useState(false);
    // Step whose "untilGone" click was made; tying it to the id keeps one click from skipping two steps.
    const [armedFor, setArmedFor] = useState<string | null>(null);
    const [tooltipSize, setTooltipSize] = useState<Size>({ width: 320, height: 160 });
    const [viewport, setViewport] = useState<Size>({ width: window.innerWidth, height: window.innerHeight });
    const tooltipRef = useRef<HTMLDivElement>(null);

    const stepId = step?.id ?? null;

    // Reset per-step state and animate the spotlight travelling to the new target.
    useEffect(() => {
        setArmedFor(null);
        setFilled(false);
        setPhase("ok");
        if (!stepId) return;
        setMoving(true);
        const timer = window.setTimeout(() => setMoving(false), MOVE_TRANSITION_MS);
        return () => window.clearTimeout(timer);
    }, [stepId]);

    // A step may open its own route (a report) and the view of it that its target lives in.
    useEffect(() => {
        if (!stepId) return;
        if (entryPath && normalizePath(window.location.pathname) !== normalizePath(entryPath)) {
            // Between reports the history entry is replaced, so closing the modal still goes back once.
            const fromReport = matchRoute("/reporte/:id", window.location.pathname).isMatch;
            navigate(entryPath, { replace: fromReport, state: { fromGraphito: true } });
        }
        if (reportView) requestReportView(reportView);
    }, [stepId, entryPath, reportView]);

    // Missing target: dim first, offer a spinner, then a way to recover.
    useEffect(() => {
        if (!step || !target.missing) {
            setPhase("ok");
            return;
        }
        const grace = step.graceMs ?? (step.fallbackRoute ? FALLBACK_GRACE_MS : DEFAULT_GRACE_MS);
        const waitingTimer = window.setTimeout(() => setPhase("waiting"), Math.min(WAITING_CHIP_MS, grace));
        const lostTimer = window.setTimeout(() => setPhase("lost"), grace);
        return () => {
            window.clearTimeout(waitingTimer);
            window.clearTimeout(lostTimer);
        };
    }, [step, target.missing]);

    // Route steps move on when the URL changes (not when a step is merely entered).
    useEffect(() => {
        if (!step || step.advance.kind !== "route") return;
        return subscribeToRoute(() => {
            if (routeAdvancesStep(step, window.location.pathname)) next(step.id);
        });
    }, [step, next]);

    // Click steps move on when the user clicks the highlighted element.
    useEffect(() => {
        if (!step || step.advance.kind !== "click") return;
        const { untilGone } = step.advance;
        const onClick = (event: MouseEvent) => {
            const clicked = event.target instanceof Element ? event.target : null;
            if (!clicked || !selectors.some((selector) => clicked.closest(selector))) return;
            // Let the app's own handler run first; it may open or close a modal.
            if (untilGone) setArmedFor(step.id);
            else window.setTimeout(() => next(step.id), 0);
        };
        document.addEventListener("click", onClick, true);
        return () => document.removeEventListener("click", onClick, true);
    }, [step, selectors, next]);

    // "untilGone" steps finish once the clicked element is gone (modal closed, button swapped).
    useEffect(() => {
        if (armedFor !== null && armedFor === stepId && target.missing) next(armedFor);
    }, [armedFor, stepId, target.missing, next]);

    // Field steps unlock "Siguiente" once the user types, pastes or loads a file.
    useEffect(() => {
        if (!step || step.advance.kind !== "filled") return;
        const check = () => setFilled(isFilled(target.element));
        check();
        const timer = window.setInterval(check, 200);
        return () => window.clearInterval(timer);
    }, [step, target.element]);

    // Esc leaves the guide instead of closing the modal underneath.
    useEffect(() => {
        if (!step) return;
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key !== "Escape") return;
            event.preventDefault();
            event.stopPropagation();
            exit();
        };
        window.addEventListener("keydown", onKeyDown, true);
        return () => window.removeEventListener("keydown", onKeyDown, true);
    }, [step, exit]);

    useEffect(() => {
        if (!step) return;
        const onResize = () => setViewport({ width: window.innerWidth, height: window.innerHeight });
        window.addEventListener("resize", onResize);
        return () => window.removeEventListener("resize", onResize);
    }, [step]);

    useLayoutEffect(() => {
        const node = tooltipRef.current;
        if (!node) return;
        const size = { width: node.offsetWidth, height: node.offsetHeight };
        setTooltipSize((prev) => (prev.width === size.width && prev.height === size.height ? prev : size));
    });

    const recover = useCallback(() => {
        if (!step) return;
        if (step.fallbackRoute) navigate(step.fallbackRoute);
        else if (step.recoverTo) goTo(step.recoverTo);
    }, [step, goTo]);

    if (!step) return null;

    const isLost = phase === "lost";
    const anchored = target.rect !== null && !isLost;
    const centered = !step.target;
    const recoverLabel = step.fallbackRoute ? "Llévame ahí" : step.recoverTo ? "Retomar" : undefined;

    const position =
        anchored && target.rect
            ? computeTooltipPosition(target.rect, tooltipSize, viewport, step.placement)
            : undefined;

    const rect = target.rect;

    return createPortal(
        <div className="fixed inset-0 z-[400] pointer-events-none" data-tour-overlay>
            {anchored && rect ? (
                <>
                    {/* Four blockers leave the target clickable and stop clicks anywhere else. */}
                    <div className="absolute pointer-events-auto" style={{ top: 0, left: 0, right: 0, height: Math.max(0, rect.top) }} />
                    <div className="absolute pointer-events-auto" style={{ top: rect.top + rect.height, left: 0, right: 0, bottom: 0 }} />
                    <div className="absolute pointer-events-auto" style={{ top: rect.top, left: 0, width: Math.max(0, rect.left), height: rect.height }} />
                    <div className="absolute pointer-events-auto" style={{ top: rect.top, left: rect.left + rect.width, right: 0, height: rect.height }} />
                    <div
                        className="tour-ring absolute"
                        style={{
                            top: rect.top,
                            left: rect.left,
                            width: rect.width,
                            height: rect.height,
                            borderRadius: target.radius,
                            boxShadow: `0 0 0 9999px ${DIM}`,
                            transition: moving
                                ? `top ${MOVE_TRANSITION_MS}ms cubic-bezier(0.16,1,0.3,1), left ${MOVE_TRANSITION_MS}ms cubic-bezier(0.16,1,0.3,1), width ${MOVE_TRANSITION_MS}ms cubic-bezier(0.16,1,0.3,1), height ${MOVE_TRANSITION_MS}ms cubic-bezier(0.16,1,0.3,1)`
                                : "none",
                        }}
                    />
                </>
            ) : (
                <div className="absolute inset-0 pointer-events-auto" style={{ background: DIM }} />
            )}

            {(anchored || centered || isLost) && (
                <TourTooltip
                    ref={tooltipRef}
                    step={step}
                    mode={isLost ? "lost" : "step"}
                    current={current}
                    total={total}
                    isFirst={state.stepIndex === 0}
                    filled={filled}
                    position={position}
                    recoverLabel={recoverLabel}
                    otherFlowLabel={state.flow === "examples" ? "Elegir otro recorrido" : "Probar el otro flujo"}
                    onNext={() => next(step.id)}
                    onBack={back}
                    onExit={exit}
                    onRecover={recover}
                    onOtherFlow={() => {
                        if (state.flow === "examples") open();
                        else if (state.flow) choose(otherFlow(state.flow));
                    }}
                />
            )}

            {phase === "waiting" && !isLost && (
                <div className="absolute bottom-8 left-1/2 -translate-x-1/2 pointer-events-none">
                    <div className="tour-pop inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white dark:bg-graphito-card border border-slate-200 dark:border-graphito-border shadow-xl text-sm font-semibold text-slate-700 dark:text-slate-200">
                        <Loader2 size={16} className="animate-spin text-graphito-blue" aria-hidden="true" />
                        Un momento…
                    </div>
                </div>
            )}
        </div>,
        document.body
    );
}
