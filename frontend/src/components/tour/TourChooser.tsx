import { useEffect, useRef, useState } from "react";
import { GitCompare, Library, Loader2, Upload, ArrowRight } from "lucide-react";
import { Modal } from "../ui/Modal";
import { api, invalidateLibrary } from "../../lib/api";
import { TOUR_FLOWS } from "../../lib/tour/steps";
import type { TourFlow } from "../../lib/tour/types";
import { useTour } from "./TourContext";

const FLOW_ICONS: Record<TourFlow, typeof Upload> = {
    own: Upload,
    library: Library,
    examples: GitCompare,
};

const EXAMPLES_ERROR = "No se pudo preparar el grupo de ejemplos. Revisa tu conexión e inténtalo de nuevo.";

export function TourChooser() {
    const { state, exit, choose } = useTour();
    const [loadingFlow, setLoadingFlow] = useState<TourFlow | null>(null);
    const [error, setError] = useState<string | null>(null);
    // A response that arrives after the chooser was closed must not start a flow.
    const isChoosing = useRef(false);

    useEffect(() => {
        isChoosing.current = state.status === "choosing";
        if (state.status !== "choosing") {
            setLoadingFlow(null);
            setError(null);
        }
    }, [state.status]);

    const pick = async (flow: TourFlow) => {
        if (loadingFlow) return;
        setError(null);
        if (flow !== "examples") {
            choose(flow);
            return;
        }
        setLoadingFlow(flow);
        try {
            const summary = await api.examples.ensure();
            if (!isChoosing.current) return;
            if (summary.creado) invalidateLibrary();
            choose(flow, summary);
        } catch (err) {
            console.warn("No se pudo preparar el grupo de ejemplos:", err);
            if (isChoosing.current) setError(EXAMPLES_ERROR);
        } finally {
            setLoadingFlow(null);
        }
    };

    return (
        <Modal
            isOpen={state.status === "choosing"}
            onClose={exit}
            maxWidth="lg"
            fixedHeight="h-auto"
            title="¿Qué quieres aprender?"
            description="Elige un recorrido y te guiamos paso a paso."
            bodyClassName="space-y-3"
        >
            {TOUR_FLOWS.map(({ flow, title, description }) => {
                const Icon = FLOW_ICONS[flow];
                const isLoading = loadingFlow === flow;
                return (
                    <button
                        key={flow}
                        type="button"
                        onClick={() => pick(flow)}
                        disabled={loadingFlow !== null}
                        aria-busy={isLoading}
                        className="group w-full flex items-center gap-4 text-left p-4 rounded-2xl border border-slate-200 dark:border-graphito-border bg-slate-50/60 dark:bg-graphito-surface/60 hover:border-graphito-blue/60 hover:bg-white dark:hover:bg-graphito-card hover:shadow-lg hover:shadow-graphito-blue/10 hover:-translate-y-0.5 active:scale-[0.99] focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue disabled:opacity-60 disabled:pointer-events-none transition-all duration-200"
                    >
                        <span className="shrink-0 w-12 h-12 rounded-xl bg-button-grad flex items-center justify-center text-white shadow-md shadow-graphito-blue/20">
                            <Icon size={22} aria-hidden="true" />
                        </span>
                        <span className="min-w-0 flex-1">
                            <span className="block font-display font-bold text-slate-900 dark:text-white">{title}</span>
                            <span className="block text-sm text-slate-600 dark:text-slate-300">
                                {isLoading ? "Preparando los ejemplos…" : description}
                            </span>
                        </span>
                        {isLoading ? (
                            <Loader2 size={18} aria-hidden="true" className="shrink-0 animate-spin text-graphito-blue" />
                        ) : (
                            <ArrowRight
                                size={18}
                                aria-hidden="true"
                                className="shrink-0 text-slate-400 group-hover:text-graphito-blue group-hover:translate-x-0.5 transition-all"
                            />
                        )}
                    </button>
                );
            })}
            {error && (
                <p role="alert" className="text-sm font-medium text-rose-600 dark:text-rose-400">
                    {error}
                </p>
            )}
        </Modal>
    );
}
