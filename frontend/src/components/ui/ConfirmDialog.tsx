import { useEffect } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { AuthCard } from "../layout/AuthCard";

interface ConfirmDialogProps {
    isOpen: boolean;
    title: string;
    message: React.ReactNode;
    confirmLabel: string;
    /** Label shown on the confirm button while `isLoading`. */
    loadingLabel?: string;
    isLoading?: boolean;
    error?: string | null;
    onConfirm: () => void;
    onCancel: () => void;
}

/** In-app replacement for window.confirm, for destructive actions. */
export function ConfirmDialog({
    isOpen,
    title,
    message,
    confirmLabel,
    loadingLabel = "Procesando...",
    isLoading = false,
    error,
    onConfirm,
    onCancel,
}: ConfirmDialogProps) {
    useEffect(() => {
        if (!isOpen) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape" && !isLoading) onCancel();
        };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [isOpen, isLoading, onCancel]);

    if (!isOpen) return null;

    return (
        <div
            className="fixed inset-0 z-[110] flex items-center justify-center p-4"
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
        >
            <div
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={isLoading ? undefined : onCancel}
            />
            <div className="relative w-full max-w-md">
                <AuthCard className="w-full p-0 overflow-hidden bg-white dark:bg-graphito-card border border-slate-200 dark:border-[#2b3346]/60 shadow-2xl rounded-2xl transition-colors">
                    <div className="flex items-start gap-4 px-8 py-6">
                        <div className="w-10 h-10 shrink-0 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-600 dark:text-red-400">
                            <AlertTriangle size={20} />
                        </div>
                        <div className="min-w-0 space-y-2">
                            <h2
                                id="confirm-dialog-title"
                                className="text-lg font-display font-bold text-slate-900 dark:text-white"
                            >
                                {title}
                            </h2>
                            <div className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                                {message}
                            </div>
                            {error && (
                                <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-600 dark:text-red-300 text-xs font-medium">
                                    {error}
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="flex items-center justify-end gap-6 px-8 py-6 border-t border-slate-200 dark:border-[#2b3346]/40 bg-slate-50 dark:bg-black/10 transition-colors">
                        <button
                            type="button"
                            onClick={onCancel}
                            disabled={isLoading}
                            className="text-sm font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 rounded-lg px-4 py-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                        >
                            Cancelar
                        </button>
                        <button
                            type="button"
                            onClick={onConfirm}
                            disabled={isLoading}
                            className="flex items-center gap-2 px-6 py-3 rounded-2xl font-display font-bold tracking-tight text-white text-sm bg-red-600 hover:bg-red-500 shadow-md shadow-red-600/20 active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0f1522] disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 transition-all"
                        >
                            {isLoading && <Loader2 size={16} className="animate-spin" />}
                            <span>{isLoading ? loadingLabel : confirmLabel}</span>
                        </button>
                    </div>
                </AuthCard>
            </div>
        </div>
    );
}
