import { ReactNode } from "react";

interface AuthCardProps {
    children: ReactNode;
    className?: string;
}

export function AuthCard({ children, className }: AuthCardProps) {
    return (
        <div className={`w-full bg-white/95 dark:bg-[#1a2031]/80 border border-slate-200/80 dark:border-[#2b3346]/40 rounded-[2.5rem] p-8 sm:p-10 shadow-xl dark:shadow-2xl shadow-slate-200/50 dark:shadow-black/50 relative z-10 backdrop-blur-md transition-all duration-300 ${className || 'max-w-[420px]'}`}>
            {children}
        </div>
    );
}

