import React, { forwardRef } from "react";
import { Loader2 } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

export type ButtonVariant = "gradient" | "primary" | "secondary" | "outline" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: ButtonVariant;
    size?: ButtonSize;
    isLoading?: boolean;
    leftIcon?: React.ReactNode;
    rightIcon?: React.ReactNode;
}

const variantStyles: Record<ButtonVariant, string> = {
    gradient:
        "relative group overflow-hidden text-white font-display tracking-tight " +
        "bg-button-grad bg-[length:100%_200%] hover:bg-bottom " +
        "shadow-[0_0_20px_rgba(59,130,246,0.2)] hover:shadow-[0_0_30px_rgba(167,139,250,0.4)] " +
        "transition-all duration-500 ease-in-out active:scale-95 " +
        "before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent " +
        "before:translate-x-[-200%] hover:before:translate-x-[200%] before:transition-transform before:duration-700",
    primary:
        "bg-graphito-blue hover:bg-blue-600 text-white shadow-sm shadow-blue-500/20 active:scale-95 transition-all duration-200",
    secondary:
        "bg-slate-100 hover:bg-slate-200 text-slate-800 dark:bg-slate-800/80 dark:hover:bg-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700/60 shadow-sm active:scale-95 transition-all duration-200",
    outline:
        "bg-transparent border border-slate-300 dark:border-[#2b3346] text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60 active:scale-95 transition-all duration-200",
    ghost:
        "bg-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800/60 active:scale-95 transition-all duration-200",
    danger:
        "bg-red-500 hover:bg-red-600 text-white shadow-sm shadow-red-500/20 dark:bg-red-600 dark:hover:bg-red-700 active:scale-95 transition-all duration-200",
};

const sizeStyles: Record<ButtonSize, string> = {
    sm: "text-xs px-3 py-1.5 rounded-lg gap-1.5 min-h-[32px]",
    md: "text-sm px-4 py-2.5 rounded-xl gap-2 min-h-[40px]",
    lg: "text-base px-6 py-3.5 rounded-2xl gap-2.5 min-h-[48px]",
};

const iconSizes: Record<ButtonSize, number> = {
    sm: 14,
    md: 16,
    lg: 20,
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    (
        {
            type = "button",
            variant = "primary",
            size = "md",
            isLoading = false,
            leftIcon,
            rightIcon,
            disabled,
            className,
            children,
            ...props
        },
        ref
    ) => {
        const isDisabled = disabled || isLoading;
        const iconSize = iconSizes[size];

        const innerContent = (
            <>
                {isLoading ? (
                    <Loader2 size={iconSize} className="animate-spin shrink-0" aria-hidden="true" />
                ) : (
                    leftIcon && <span className="shrink-0 flex items-center">{leftIcon}</span>
                )}
                {children && <span>{children}</span>}
                {rightIcon && !isLoading && <span className="shrink-0 flex items-center">{rightIcon}</span>}
            </>
        );

        return (
            <button
                ref={ref}
                type={type}
                disabled={isDisabled}
                aria-busy={isLoading || undefined}
                aria-disabled={isDisabled || undefined}
                className={cn(
                    "inline-flex items-center justify-center font-bold select-none cursor-pointer text-center",
                    "focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue focus-visible:ring-offset-2 focus-visible:ring-offset-white dark:focus-visible:ring-offset-[#0f172a]",
                    "disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none disabled:active:scale-100",
                    variantStyles[variant],
                    sizeStyles[size],
                    className
                )}
                {...props}
            >
                {variant === "gradient" ? (
                    <span className="relative z-10 flex items-center justify-center gap-2">
                        {innerContent}
                    </span>
                ) : (
                    innerContent
                )}
            </button>
        );
    }
);

Button.displayName = "Button";
