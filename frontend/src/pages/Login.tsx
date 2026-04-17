import { useState } from "react";
import { AtSign, Lock, Eye, EyeOff } from "lucide-react";
import logo from "../assets/logo.png";
import { AuthCard } from "../components/layout/AuthCard";

// Icono simple de Google
const GoogleIcon = () => (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="w-5 h-5">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
);

interface LoginProps {
    onLogin?: () => void;
    onNavigateToRegister?: () => void;
}

export function Login({ onLogin, onNavigateToRegister }: LoginProps) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);

    return (
        <div className="flex-1 w-full flex flex-col items-center justify-center p-4">
            <AuthCard>
                {/* Header de la tarjeta */}
                <div className="flex flex-col items-center mb-10">
                    <div className="flex items-center gap-3 mb-4">
                        <img src={logo} alt="Graphito Logo" className="w-10 h-10 object-contain" />
                        <h1 className="text-4xl font-display font-extrabold tracking-tight bg-gradient-to-r from-graphito-blue to-graphito-violet bg-clip-text text-transparent">
                            Graphito
                        </h1>
                    </div>
                    <p className="text-sm text-slate-300 font-medium">
                        Compara. Analiza. Comprende tu código.
                    </p>
                </div>

                {/* Botón Google */}
                <button className="w-full flex items-center justify-center gap-3 bg-white text-gray-900 rounded-2xl py-3.5 px-4 font-bold hover:bg-gray-100 transition-colors shadow-sm text-[15px]">
                    <GoogleIcon />
                    Continuar con Google
                </button>

                {/* Separador */}
                <div className="flex items-center my-6">
                    <div className="flex-grow border-t border-[#2b3346]"></div>
                    <span className="mx-4 text-[10px] font-bold text-slate-500 uppercase">o</span>
                    <div className="flex-grow border-t border-[#2b3346]"></div>
                </div>

                {/* Formulario manual */}
                <form onSubmit={(e) => { e.preventDefault(); onLogin?.(); }} className="space-y-5">
                    {/* Email */}
                    <div className="space-y-2">
                        <label className="text-[13px] font-bold text-slate-200 ml-1">
                            Correo electrónico
                        </label>
                        <div className="relative group">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-graphito-blue transition-colors">
                                <AtSign size={18} />
                            </div>
                            <input
                                type="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="nombre@ejemplo.com"
                                className="w-full bg-[#121827]/30 border border-[#2b3346] text-white rounded-2xl py-3.5 pl-12 pr-4 focus:outline-none focus:ring-2 focus:ring-graphito-blue/50 focus:border-graphito-blue transition-all placeholder:text-slate-500 font-medium text-[15px]"
                            />
                        </div>
                    </div>

                    {/* Password */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between ml-1">
                            <label className="text-[13px] font-bold text-slate-200">
                                Contraseña
                            </label>
                            <button type="button" className="text-[10px] font-bold text-graphito-violet hover:text-white transition-colors uppercase tracking-wider">
                                ¿Olvidaste tu contraseña?
                            </button>
                        </div>
                        <div className="relative group">
                            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-graphito-blue transition-colors">
                                <Lock size={18} />
                            </div>
                            <input
                                type={showPassword ? "text" : "password"}
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                className="w-full bg-[#121827]/30 border border-[#2b3346] text-white rounded-2xl py-3.5 pl-12 pr-12 focus:outline-none focus:ring-2 focus:ring-graphito-blue/50 focus:border-graphito-blue transition-all placeholder:text-slate-500 text-[15px] tracking-widest font-mono"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute inset-y-0 right-0 pr-4 flex items-center text-slate-400 hover:text-white transition-colors"
                                aria-label="Toggle password visibility"
                            >
                                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>
                    </div>

                    {/* Submit */}
                    <button
                        type="submit"
                        className="w-full bg-gradient-to-r from-graphito-blue to-graphito-violet text-white font-bold rounded-2xl py-4 mt-2 hover:opacity-90 transition-opacity shadow-lg shadow-graphito-blue/20 text-[15px]"
                    >
                        Iniciar sesión
                    </button>
                </form>

                {/* Footer text */}
                <div className="mt-8 text-center">
                    <p className="text-[13px] text-slate-400 font-medium">
                        ¿No tienes una cuenta? <button onClick={onNavigateToRegister} className="text-white hover:text-graphito-violet font-bold transition-colors ml-1">Crear cuenta</button>
                    </p>
                </div>
            </AuthCard>

            {/* Badge ESCOM */}
            <div className="absolute bottom-6 flex items-center justify-center">
                <div className="flex items-center gap-2 bg-[#1a2031]/60 border border-[#2b3346] rounded-full px-4 py-2 backdrop-blur-md">
                    <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full"></div>
                    <span className="text-[10px] uppercase font-bold tracking-widest text-slate-300">
                        Graphito ESCOM IPN
                    </span>
                </div>
            </div>
        </div>
    );
}
