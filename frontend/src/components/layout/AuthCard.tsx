import { ReactNode } from "react";

interface AuthCardProps {
    children: ReactNode;
    className?: string;
}

export function AuthCard({ children, className }: AuthCardProps) {
    return (
        <div className={`w-full bg-white/85 dark:bg-[#151c2e]/80 border border-slate-200/80 dark:border-white/[0.09] rounded-[2.5rem] p-8 sm:p-10 shadow-2xl shadow-black/15 dark:shadow-black/60 relative z-10 backdrop-blur-xl transition-all duration-300 ${className || 'max-w-[420px]'}`}>
            {children}
        </div>
    );
}

