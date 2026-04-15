import React from 'react';

interface GradientButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    children: React.ReactNode;
}

export function GradientButton({ children, className, ...props }: GradientButtonProps) {
    return (
        <button
            {...props}
            className={`
        relative group overflow-hidden px-6 py-2.5 rounded-xl font-bold text-white
        
        /* 1. Tu degradado personalizado */
        bg-button-grad bg-[length:100%_200%] hover:bg-bottom
        
        /* 2. Tu tipografía display */
        font-display tracking-tight
        
        /* 3. Iluminación usando tu graphito-blue */
        shadow-[0_0_20px_rgba(59,130,246,0.2)]
        hover:shadow-[0_0_30px_rgba(167,139,250,0.4)]
        
        /* 4. Efectos de interacción */
        transition-all duration-500 ease-in-out
        active:scale-95
        
        /* 5. Reflejo interno (Glow) */
        before:absolute before:inset-0
        before:bg-gradient-to-r before:from-transparent before:via-white/20 before:to-transparent
        before:translate-x-[-200%] hover:before:translate-x-[200%]
        before:transition-transform before:duration-700
        
        ${className}
      `}
        >
            <span className="relative z-10 flex items-center gap-2">
                {children}
            </span>
        </button>
    );
}