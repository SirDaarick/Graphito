import { Eye, EyeOff } from "lucide-react";

interface PasswordToggleProps {
    shown: boolean;
    onToggle: () => void;
}

/** Eye button that sits inside a password field (the field needs `relative` and right padding). */
export function PasswordToggle({ shown, onToggle }: PasswordToggleProps) {
    return (
        <button
            type="button"
            onClick={onToggle}
            aria-label={shown ? "Ocultar contraseña" : "Mostrar contraseña"}
            aria-pressed={shown}
            title={shown ? "Ocultar contraseña" : "Mostrar contraseña"}
            className="absolute inset-y-0 right-0 flex w-12 items-center justify-center rounded-r-2xl text-slate-500 transition-colors hover:text-graphito-blue focus:outline-none focus-visible:ring-2 focus-visible:ring-graphito-blue dark:text-slate-400 dark:hover:text-white"
        >
            {shown ? <EyeOff size={20} aria-hidden="true" /> : <Eye size={20} aria-hidden="true" />}
        </button>
    );
}
