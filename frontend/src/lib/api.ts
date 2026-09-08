/**
 * Graphito Backend API Client
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

class ApiError extends Error {
    constructor(public status: number, message: string) {
        super(message);
        this.name = "ApiError";
    }
}

function getAuthToken(): string | null {
    return localStorage.getItem("graphito_token");
}

export function setAuthToken(token: string | null) {
    if (token) {
        localStorage.setItem("graphito_token", token);
    } else {
        localStorage.removeItem("graphito_token");
    }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(options.headers as Record<string, string>),
    };

    const token = getAuthToken();
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers,
    });

    if (!response.ok) {
        let errorMessage = `HTTP Error ${response.status}`;
        try {
            const errData = await response.json();
            errorMessage = errData.detail || errorMessage;
        } catch {
            // fallback
        }
        throw new ApiError(response.status, errorMessage);
    }

    return response.json();
}

export interface Docente {
    id: number;
    email: string;
    nombre: string;
    created_at: string;
}

export interface Problema {
    id: number;
    docente_id: number;
    titulo: string;
    enunciado: string;
    lenguaje: string;
    fecha_creacion: string;
}

export interface CodigoFuente {
    id: string;
    problema_id: number;
    tipo: "REFERENCIA" | "ENTREGA_ALUMNO";
    autor: string;
    contenido: string;
    lenguaje: string;
    created_at: string;
}

export interface IndicadorIntegridad {
    id?: number;
    tipo_alerta: string;
    descripcion: string;
    severidad: "BAJA" | "MEDIA" | "ALTA" | "CRITICA";
}

export interface ReporteAnalisis {
    id: number;
    entrega_id: string;
    referencia_id?: string;
    similitud_semantica: number;
    probabilidad_ia: number;
    discrepancia_score: number;
    dictamen: "INTEGRO" | "SOSPECHA_IA" | "PLAGIO_PROBABLE";
    fecha_analisis: string;
    indicadores: IndicadorIntegridad[];
}

export const api = {
    auth: {
        async register(email: string, password: string, nombre: string): Promise<Docente> {
            return request<Docente>("/auth/register", {
                method: "POST",
                body: JSON.stringify({ email, password, nombre }),
            });
        },
        async login(email: string, password: string): Promise<{ access_token: string; docente: Docente }> {
            const res = await request<{ access_token: string; docente: Docente }>("/auth/login", {
                method: "POST",
                body: JSON.stringify({ email, password }),
            });
            setAuthToken(res.access_token);
            return res;
        },
        async me(): Promise<Docente> {
            return request<Docente>("/auth/me");
        },
        logout() {
            setAuthToken(null);
        },
        isAuthenticated(): boolean {
            return !!getAuthToken();
        }
    },

    problems: {
        async list(): Promise<Problema[]> {
            return request<Problema[]>("/problems/");
        },
        async create(titulo: string, enunciado: string, lenguaje = "c"): Promise<Problema> {
            return request<Problema>("/problems/", {
                method: "POST",
                body: JSON.stringify({ titulo, enunciado, lenguaje }),
            });
        },
        async get(id: number): Promise<Problema> {
            return request<Problema>(`/problems/${id}`);
        },
        async addReference(problemId: number, autor: string, contenido: string, lenguaje = "c"): Promise<CodigoFuente> {
            const params = new URLSearchParams({ autor, contenido, lenguaje });
            return request<CodigoFuente>(`/problems/${problemId}/references?${params.toString()}`, {
                method: "POST",
            });
        },
        async addSubmission(problemId: number, autor: string, contenido: string, lenguaje = "c"): Promise<CodigoFuente> {
            return request<CodigoFuente>(`/problems/${problemId}/submissions`, {
                method: "POST",
                body: JSON.stringify({
                    problema_id: problemId,
                    autor,
                    contenido,
                    lenguaje,
                    tipo: "ENTREGA_ALUMNO",
                }),
            });
        },
        async listSubmissions(problemId: number): Promise<CodigoFuente[]> {
            return request<CodigoFuente[]>(`/problems/${problemId}/submissions`);
        }
    },

    analysis: {
        async run(entregaId: string, referenciaId?: string, thresholdSem = 0.85, thresholdAi = 0.70): Promise<ReporteAnalisis> {
            return request<ReporteAnalisis>("/analysis/run", {
                method: "POST",
                body: JSON.stringify({
                    entrega_id: entregaId,
                    referencia_id: referenciaId || null,
                    threshold_sem: thresholdSem,
                    threshold_ai: thresholdAi,
                }),
            });
        },
        async getReport(reportId: number): Promise<ReporteAnalisis> {
            return request<ReporteAnalisis>(`/analysis/reports/${reportId}`);
        }
    }
};
