import { ReactNode } from "react";
import { InfoPopover } from "../ui/InfoPopover";

interface RadialProgressCardProps {
    title: string;
    centerLabel: string;
    pct: number | null;
    description: string;
    unavailableReason?: string | null;
    helpLabel: string;
    helpTitle: string;
    help: ReactNode;
    accent: "blue" | "violet";
    animate: boolean;
}

const ACCENT = {
    blue: {
        gradientStart: "#38bdf8",
        gradientEnd: "#2563eb",
        badge: "bg-graphito-blue/10 text-graphito-blue border-graphito-blue/20",
    },
    violet: {
        gradientStart: "#c084fc",
        gradientEnd: "#7c3aed",
        badge: "bg-graphito-violet/10 text-graphito-violet border-graphito-violet/20",
    },
} as const;

/**
 * Radial Chart - Text component following shadcn/ui design standards.
 * Features an animated circular SVG track, center percentage callout,
 * accessible ARIA progressbar attributes, and an integrated help popover.
 */
export function RadialProgressCard({
    title,
    centerLabel,
    pct,
    description,
    unavailableReason,
    helpLabel,
    helpTitle,
    help,
    accent,
    animate,
}: RadialProgressCardProps) {
    const config = ACCENT[accent];
    const available = pct !== null;
    const radius = 54;
    const circumference = 2 * Math.PI * radius; // ~339.292
    const strokeDashoffset = available
        ? circumference * (1 - (animate ? pct : 0) / 100)
        : circumference;

    return (
        <article className="relative flex flex-col justify-between rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-[#2b3346]/60 dark:bg-[#121827]/40">
            {/* Header: Title + Info Popover */}
            <div className="flex items-center justify-between gap-3 mb-2">
                <h4 className="text-sm font-bold text-slate-900 dark:text-white leading-snug">
                    {title}
                </h4>
                <InfoPopover label={helpLabel} title={helpTitle} className="shrink-0">
                    {help}
                </InfoPopover>
            </div>

            {/* Radial Chart - Text container */}
            <div className="relative w-36 h-36 my-2 mx-auto flex items-center justify-center">
                <svg
                    className="w-full h-full transform -rotate-90"
                    viewBox="0 0 140 140"
                    role="progressbar"
                    aria-label={title}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={available ? pct : undefined}
                >
                    <defs>
                        <linearGradient
                            id={`radial-gradient-${accent}`}
                            x1="0%"
                            y1="0%"
                            x2="100%"
                            y2="100%"
                        >
                            <stop offset="0%" stopColor={config.gradientStart} />
                            <stop offset="100%" stopColor={config.gradientEnd} />
                        </linearGradient>
                    </defs>

                    {/* Background Track */}
                    <circle
                        cx="70"
                        cy="70"
                        r={radius}
                        className="stroke-slate-100 dark:stroke-[#2b3346]/40"
                        strokeWidth="11"
                        fill="transparent"
                    />

                    {/* Progress Arc */}
                    {available && (
                        <circle
                            cx="70"
                            cy="70"
                            r={radius}
                            stroke={`url(#radial-gradient-${accent})`}
                            strokeWidth="11"
                            strokeDasharray={circumference}
                            strokeDashoffset={strokeDashoffset}
                            strokeLinecap="round"
                            fill="transparent"
                            className="transition-all duration-1000 ease-out motion-reduce:transition-none"
                        />
                    )}
                </svg>

                {/* Center Text */}
                <div className="absolute inset-0 flex flex-col items-center justify-center text-center select-none pointer-events-none">
                    {available ? (
                        <>
                            <span className="text-3xl font-display font-extrabold text-slate-900 dark:text-white tracking-tight leading-none">
                                {pct}
                                <span className="text-xl font-bold text-slate-400 dark:text-slate-500">
                                    %
                                </span>
                            </span>
                            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 dark:text-slate-500 mt-1">
                                {centerLabel}
                            </span>
                        </>
                    ) : (
                        <>
                            <span className="text-sm font-bold text-slate-400 dark:text-slate-500">
                                N/A
                            </span>
                            <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 dark:text-slate-500 mt-0.5">
                                No disponible
                            </span>
                        </>
                    )}
                </div>
            </div>

            {/* Footer: Concise Description */}
            <p className="mt-4 text-xs text-center text-slate-500 dark:text-slate-400 leading-relaxed min-h-[32px] flex items-center justify-center">
                {available ? description : (unavailableReason ?? description)}
            </p>
        </article>
    );
}
