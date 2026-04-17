import { ReactNode } from "react";

interface AuthCardProps {
    children: ReactNode;
    className?: string;
}

export function AuthCard({ children, className }: AuthCardProps) {
    return (
        <div className={`w-full bg-[#1a2031]/65 border border-[#2b3346]/40 rounded-[2.5rem] p-8 sm:p-10 shadow-2xl relative z-10 backdrop-blur-xl transition-all duration-300 ${className || 'max-w-[420px]'}`}>
            {children}
        </div>
    );
}
