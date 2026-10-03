/**
 * Graphito Backend API Client
 */

import {
    DEMO_DOCENTE,
    DEMO_PROBLEMAS,
    DEMO_SUBMISSIONS,
    DEMO_REPORTS,
    DEMO_CODE_COMPARISONS,
    DEMO_COMMENTS,
} from "./demoData";

export const IS_DEMO_MODE: boolean =
    import.meta.env.DEMO_MODE === "true" ||
    import.meta.env.VITE_DEMO_MODE === "true";

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
        "ngrok-skip-browser-warning": "true",
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
    reporte?: ReporteAnalisis;
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
    dictamen: "SIN_ALERTAS" | "REVISION_ESTILOMETRICA" | "REVISION_SEMANTICA" | "DISCREPANCIA_DUAL" | "INTEGRO" | "SOSPECHA_IA" | "PLAGIO_PROBABLE";
    estado?: "PENDIENTE" | "PROCESANDO" | "COMPLETADO" | "ERROR";
    error_mensaje?: string;
    indicadores: IndicadorIntegridad[];
}

export interface ReportCodeComparison {
    reporte_id: number;
    student_author: string;
    student_code: string;
    reference_author: string;
    reference_code: string;
    language: string;
    problem_title: string;
}

export interface ComentarioRevision {
    id: number;
    reporte_id: number;
    docente_id: number;
    numero_linea: number | null;
    contenido: string;
    created_at: string;
    autor_nombre?: string;
}

// In-memory comments store for demo mode
const demoCommentsStore: Record<number, ComentarioRevision[]> = JSON.parse(JSON.stringify(DEMO_COMMENTS));

export const api = {
    auth: {
        async register(email: string, password: string, nombre: string): Promise<Docente> {
            if (IS_DEMO_MODE) {
                return DEMO_DOCENTE;
            }
            return request<Docente>("/auth/register", {
                method: "POST",
                body: JSON.stringify({ email, password, nombre }),
            });
        },
        async login(email: string, password: string): Promise<{ access_token: string; docente: Docente }> {
            if (IS_DEMO_MODE) {
                setAuthToken("demo_token_showcase");
                return { access_token: "demo_token_showcase", docente: DEMO_DOCENTE };
            }
            const res = await request<{ access_token: string; docente: Docente }>("/auth/login", {
                method: "POST",
                body: JSON.stringify({ email, password }),
            });
            setAuthToken(res.access_token);
            return res;
        },
        async googleLogin(idToken: string): Promise<{ access_token: string; docente: Docente }> {
            if (IS_DEMO_MODE) {
                setAuthToken("demo_token_showcase");
                return { access_token: "demo_token_showcase", docente: DEMO_DOCENTE };
            }
            const res = await request<{ access_token: string; docente: Docente }>("/auth/google", {
                method: "POST",
                body: JSON.stringify({ token: idToken }),
            });
            setAuthToken(res.access_token);
            return res;
        },
        async me(): Promise<Docente> {
            if (IS_DEMO_MODE) {
                return DEMO_DOCENTE;
            }
            return request<Docente>("/auth/me");
        },
        logout() {
            setAuthToken(null);
        },
        isAuthenticated(): boolean {
            if (IS_DEMO_MODE) {
                return true;
            }
            return !!getAuthToken();
        }
    },

    problems: {
        async list(): Promise<Problema[]> {
            if (IS_DEMO_MODE) {
                return DEMO_PROBLEMAS;
            }
            return request<Problema[]>("/problems/");
        },
        async create(titulo: string, enunciado: string, lenguaje = "c"): Promise<Problema> {
            if (IS_DEMO_MODE) {
                throw new ApiError(403, "El modo demo está configurado en solo lectura para exhibición.");
            }
            return request<Problema>("/problems/", {
                method: "POST",
                body: JSON.stringify({ titulo, enunciado, lenguaje }),
            });
        },
        async get(id: number): Promise<Problema> {
            if (IS_DEMO_MODE) {
                const found = DEMO_PROBLEMAS.find(p => p.id === id);
                if (found) return found;
                return DEMO_PROBLEMAS[0];
            }
            return request<Problema>(`/problems/${id}`);
        },
        async addReference(problemId: number, autor: string, contenido: string, lenguaje = "c"): Promise<CodigoFuente> {
            if (IS_DEMO_MODE) {
                throw new ApiError(403, "El modo demo no permite subir nuevas referencias (solo lectura).");
            }
            const params = new URLSearchParams({ autor, contenido, lenguaje });
            return request<CodigoFuente>(`/problems/${problemId}/references?${params.toString()}`, {
                method: "POST",
            });
        },
        async addSubmission(problemId: number, autor: string, contenido: string, lenguaje = "c"): Promise<CodigoFuente> {
            if (IS_DEMO_MODE) {
                throw new ApiError(403, "El modo demo no permite subir nuevos archivos de entrega (solo lectura).");
            }
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
            if (IS_DEMO_MODE) {
                return DEMO_SUBMISSIONS[problemId] || [];
            }
            return request<CodigoFuente[]>(`/problems/${problemId}/submissions`);
        }
    },

    analysis: {
        async run(
            entregaId: string,
            referenciaId?: string,
            thresholdSem = 0.85,
            thresholdAi = 0.70,
            asyncMode = true
        ): Promise<ReporteAnalisis> {
            if (IS_DEMO_MODE) {
                return DEMO_REPORTS[101];
            }
            return request<ReporteAnalisis>(`/analysis/run?async_mode=${asyncMode}`, {
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
            if (IS_DEMO_MODE) {
                return DEMO_REPORTS[reportId] || DEMO_REPORTS[101];
            }
            return request<ReporteAnalisis>(`/analysis/reports/${reportId}`);
        },
        async pollUntilComplete(
            reportId: number,
            timeoutMs = 60000,
            intervalMs = 1000
        ): Promise<ReporteAnalisis> {
            if (IS_DEMO_MODE) {
                return DEMO_REPORTS[reportId] || DEMO_REPORTS[101];
            }
            const startTime = Date.now();
            while (Date.now() - startTime < timeoutMs) {
                const rep = await api.analysis.getReport(reportId);
                if (rep.estado === "COMPLETADO") {
                    return rep;
                }
                if (rep.estado === "ERROR") {
                    throw new Error(rep.error_mensaje || "Error durante el análisis bimodal en segundo plano");
                }
                await new Promise((resolve) => setTimeout(resolve, intervalMs));
            }
            throw new Error("Tiempo de espera agotado esperando el reporte de análisis.");
        },
        async downloadPdf(reportId: number, filename?: string): Promise<void> {
            if (IS_DEMO_MODE) {
                const rep = DEMO_REPORTS[reportId] || DEMO_REPORTS[101];
                const codeComp = DEMO_CODE_COMPARISONS[reportId] || DEMO_CODE_COMPARISONS[101];
                const textContent = [
                    "========================================================",
                    "REPORTE DE INTEGRIDAD ACADÉMICA - GRAPHITO (MODO DEMO)",
                    "========================================================",
                    "",
                    `Problema: ${codeComp.problem_title}`,
                    `Estudiante Evaluado: ${codeComp.student_author}`,
                    `Dictamen Automático: ${rep.dictamen}`,
                    `Similitud Semántica (AST / DFG): ${(rep.similitud_semantica * 100).toFixed(1)}%`,
                    `Probabilidad Generación IA (CharCNN): ${(rep.probabilidad_ia * 100).toFixed(1)}%`,
                    `Discrepancia Score: ${rep.discrepancia_score}`,
                    "",
                    "Indicadores de Integridad:",
                    ...(rep.indicadores.length > 0
                        ? rep.indicadores.map(i => `  • [${i.severidad}] ${i.tipo_alerta}: ${i.descripcion}`)
                        : ["  • Sin alertas críticas detectadas."]),
                    "",
                    "Docente Evaluador: Dr. Alan Turing",
                    "Plataforma: Graphito In-Memory Demonstration",
                    "========================================================",
                ].join("\n");

                const blob = new Blob([textContent], { type: "text/plain;charset=utf-8" });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = filename || `reporte_integridad_${reportId}.txt`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                return;
            }

            const token = getAuthToken();
            const headers: Record<string, string> = {
                "ngrok-skip-browser-warning": "true",
            };
            if (token) {
                headers["Authorization"] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_BASE_URL}/analysis/reports/${reportId}/pdf`, {
                headers,
            });

            if (!response.ok) {
                throw new Error(`Error descargando PDF: ${response.statusText}`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = filename || `reporte_integridad_${reportId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        },
        async getCode(reportId: number): Promise<ReportCodeComparison> {
            if (IS_DEMO_MODE) {
                return DEMO_CODE_COMPARISONS[reportId] || DEMO_CODE_COMPARISONS[101];
            }
            return request<ReportCodeComparison>(`/analysis/reports/${reportId}/code`);
        }
    },

    comments: {
        async list(reportId: number): Promise<ComentarioRevision[]> {
            if (IS_DEMO_MODE) {
                return demoCommentsStore[reportId] || [];
            }
            return request<ComentarioRevision[]>(`/reports/${reportId}/comments`);
        },
        async create(
            reportId: number,
            data: { numero_linea?: number | null; contenido: string }
        ): Promise<ComentarioRevision> {
            if (IS_DEMO_MODE) {
                const newComment: ComentarioRevision = {
                    id: Date.now(),
                    reporte_id: reportId,
                    docente_id: 1,
                    numero_linea: data.numero_linea || null,
                    contenido: data.contenido,
                    created_at: new Date().toISOString(),
                    autor_nombre: DEMO_DOCENTE.nombre,
                };
                if (!demoCommentsStore[reportId]) {
                    demoCommentsStore[reportId] = [];
                }
                demoCommentsStore[reportId].push(newComment);
                return newComment;
            }
            return request<ComentarioRevision>(`/reports/${reportId}/comments`, {
                method: "POST",
                body: JSON.stringify(data),
            });
        },
        async delete(reportId: number, commentId: number): Promise<void> {
            if (IS_DEMO_MODE) {
                if (demoCommentsStore[reportId]) {
                    demoCommentsStore[reportId] = demoCommentsStore[reportId].filter(c => c.id !== commentId);
                }
                return;
            }
            return request<void>(`/reports/${reportId}/comments/${commentId}`, {
                method: "DELETE",
            });
        }
    }
};