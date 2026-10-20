import type { ReactNode } from "react";
import { InfoPopover } from "../ui/InfoPopover";

interface MetricCardProps {
    title: string;
    /** Whole percentage, or null when the measurement is not available. */
    pct: number | null;
    /** One plain sentence explaining what the number means. */
    description: string;
    /** Shown instead of the number when pct is null. */
    unavailableReason?: string | null;
    helpLabel: string;
    helpTitle: string;
    help: ReactNode;
    accent: "blue" | "violet";
    /** Fill the bar (lets the width animate in after the modal opens). */
    animate: boolean;
}

const ACCENT = {
    blue: { bar: "bg-graphito-blue", icon: "bg-graphito-blue/10 text-graphito-blue" },
    violet: { bar: "bg-graphito-violet", icon: "bg-graphito-violet/10 text-graphito-violet" },
} as const;

/** One metric: only the percentage, one plain sentence, and a "?" with the full explanation. */
export function MetricCard({ title, pct, description, unavailableReason, helpLabel, helpTitle, help, accent, animate }: MetricCardProps) {
    const colors = ACCENT[accent];
    const available = pct !== null;

    return (
        <article className="relative rounded-3xl border border-slate-200 bg-slate-50 p-5 dark:border-[#2b3346]/60 dark:bg-[#121827]/40">
            <InfoPopover label={helpLabel} title={helpTitle} className="absolute right-3 top-3">
                {help}
            </InfoPopover>

            <h4 className="pr-10 text-sm font-bold text-slate-900 dark:text-white">{title}</h4>

            {available ? (
                <>
                    <p className="mt-2 text-4xl font-black tracking-tight text-slate-900 dark:text-white">
                        {pct}
                        <span className="text-2xl font-bold text-slate-500 dark:text-slate-400"> %</span>
                    </p>
                    <div
                        className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-[#2b3346]/60"
                        role="progressbar"
                        aria-label={title}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={pct}
                    >
                        <div
                            className={`h-full rounded-full ${colors.bar} transition-all duration-1000 ease-out motion-reduce:transition-none`}
                            style={{ width: animate ? `${pct}%` : "0%" }}
                        />
                    </div>
                    <p className="mt-3 text-xs leading-relaxed text-slate-600 dark:text-slate-400">{description}</p>
                </>
            ) : (
                <>
                    <p className="mt-2 text-2xl font-bold tracking-tight text-slate-500 dark:text-slate-400">No disponible</p>
                    <p className="mt-3 text-xs leading-relaxed text-slate-600 dark:text-slate-400">{unavailableReason ?? description}</p>
                </>
            )}
        </article>
    );
}
