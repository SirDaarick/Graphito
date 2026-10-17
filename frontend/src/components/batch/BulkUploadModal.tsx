import { useState, useRef, useEffect } from "react";
import {
    X,
    UploadCloud,
    Folder,
    FileCode2,
    Users,
    Trash2,
    CheckCircle2,
    Loader2,
    Sparkles,
    AlertCircle,
    Edit3,
} from "lucide-react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { AuthCard } from "../layout/AuthCard";
import { GradientButton } from "../ui/GradientButton";
import { api, Problema, Grupo, IS_DEMO_MODE } from "../../lib/api";
import { parseStudentFilename, ParsedStudentFile } from "../../lib/filename_parser";

interface BulkUploadModalProps {
    isOpen: boolean;
    onClose: () => void;
    onBatchComplete: () => void;
    preselectedProblemId?: number | null;
    preselectedGroupId?: number | null;
}

export function BulkUploadModal({
    isOpen,
    onClose,
    onBatchComplete,
    preselectedProblemId,
    preselectedGroupId,
}: BulkUploadModalProps) {
    const [problems, setProblems] = useState<Problema[]>([]);
    const [groups, setGroups] = useState<Grupo[]>([]);
    const [selectedProblemId, setSelectedProblemId] = useState<number | null>(preselectedProblemId || null);
    const [selectedGroupId, setSelectedGroupId] = useState<number | null>(preselectedGroupId || null);

    const [files, setFiles] = useState<ParsedStudentFile[]>([]);
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [batchId, setBatchId] = useState<string | null>(null);
    const [progressPercent, setProgressPercent] = useState<number>(0);
    const [processedCount, setProcessedCount] = useState<number>(0);
    const [totalCount, setTotalCount] = useState<number>(0);
    const [isCompleted, setIsCompleted] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [shouldRender, setShouldRender] = useState(isOpen);
    const backdropRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);
    const filesInputRef = useRef<HTMLInputElement>(null);
    const folderInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (isOpen) {
            setShouldRender(true);
            setError(null);
            setIsCompleted(false);
            setBatchId(null);
            setProgressPercent(0);

            // Cargar problemas y grupos
            Promise.all([api.problems.list(), api.groups.list()])
                .then(([probList, grpList]) => {
                    setProblems(probList);
                    setGroups(grpList);
                    if (preselectedProblemId && probList.some((p) => p.id === preselectedProblemId)) {
                        setSelectedProblemId(preselectedProblemId);
                    } else if (!selectedProblemId && probList.length > 0) {
                        setSelectedProblemId(probList[0].id);
                    }
                })
                .catch(() => {});
        }
    }, [isOpen]);

    useGSAP(() => {
        if (!shouldRender) return;

        if (isOpen) {
            gsap.fromTo(
                backdropRef.current,
                { opacity: 0 },
                { opacity: 1, duration: 0.25, ease: "power2.out" }
            );
            gsap.fromTo(
                contentRef.current,
                { opacity: 0, scale: 0.95, y: 15 },
                { opacity: 1, scale: 1, y: 0, duration: 0.35, ease: "back.out(1.2)" }
            );
        } else {
            gsap.to(backdropRef.current, { opacity: 0, duration: 0.2, ease: "power2.in" });
            gsap.to(contentRef.current, {
                opacity: 0,
                scale: 0.95,
                y: 10,
                duration: 0.2,
                ease: "power2.in",
                onComplete: () => setShouldRender(false),
            });
        }
    }, [isOpen, shouldRender]);

    const handleFilesSelected = (selectedFiles: FileList | File[]) => {
        const validExtensions = [".c", ".cpp", ".cc", ".cxx", ".h"];
        const newParsed: ParsedStudentFile[] = [];

        Array.from(selectedFiles).forEach((f) => {
            const hasValidExt = validExtensions.some((ext) => f.name.toLowerCase().endsWith(ext));
            if (hasValidExt) {
                newParsed.push(parseStudentFilename(f));
            }
        });

        if (newParsed.length === 0) {
            setError("No se encontraron archivos de código fuente válidos (.c, .cpp, .cc).");
            return;
        }

        setError(null);
        setFiles((prev) => {
            // Evitar duplicados por nombre de archivo
            const existingNames = new Set(prev.map((p) => p.filename));
            const filteredNew = newParsed.filter((p) => !existingNames.has(p.filename));
            return [...prev, ...filteredNew];
        });
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        if (e.dataTransfer.files) {
            handleFilesSelected(e.dataTransfer.files);
        }
    };

    const handleAuthorChange = (index: number, newAuthor: string) => {
        setFiles((prev) => {
            const updated = [...prev];
            updated[index].authorName = newAuthor;
            return updated;
        });
    };

    const handleRemoveFile = (index: number) => {
        setFiles((prev) => prev.filter((_, i) => i !== index));
    };

    const handleStartBatch = async () => {
        if (!selectedProblemId) {
            setError("Debes seleccionar el problema o tarea al que corresponden estas entregas.");
            return;
        }
        if (files.length === 0) {
            setError("Debes cargar al menos un archivo de código fuente.");
            return;
        }

        setIsUploading(true);
        setError(null);
        setTotalCount(files.length);
        setProcessedCount(0);
        setProgressPercent(0);

        try {
            const rawFiles = files.map((f) => f.file);
            const response = await api.analysis.uploadBatch(
                selectedProblemId,
                rawFiles,
                selectedGroupId || undefined
            );

            setBatchId(response.batch_id);

            // Iniciar sondeo (Polling) del lote
            if (IS_DEMO_MODE) {
                // Simulación animada para Demo Mode
                let current = 0;
                const interval = setInterval(() => {
                    current += 1;
                    const percent = Math.min(100, Math.round((current / files.length) * 100));
                    setProcessedCount(current);
                    setProgressPercent(percent);

                    if (current >= files.length) {
                        clearInterval(interval);
                        setIsCompleted(true);
                        setIsUploading(false);
                        onBatchComplete();
                    }
                }, 800);
            } else {
                const pollInterval = setInterval(async () => {
                    try {
                        const status = await api.analysis.getBatchStatus(response.batch_id);
                        setProcessedCount(status.procesados);
                        setTotalCount(status.total_archivos);
                        setProgressPercent(status.porcentaje);

                        if (status.estado === "COMPLETADO") {
                            clearInterval(pollInterval);
                            setIsCompleted(true);
                            setIsUploading(false);
                            onBatchComplete();
                        } else if (status.estado === "ERROR") {
                            clearInterval(pollInterval);
                            setIsUploading(false);
                            setError("Ocurrió un error durante el procesamiento del lote.");
                        }
                    } catch (pollErr) {
                        console.error("Error al sondear estado del lote:", pollErr);
                    }
                }, 1500);
            }
        } catch (err: any) {
            setIsUploading(false);
            setError(err.message || "Error al iniciar el análisis masivo.");
        }
    };

    if (!shouldRender) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <div
                ref={backdropRef}
                onClick={isUploading ? undefined : onClose}
                className="absolute inset-0 bg-background/80 backdrop-blur-md"
            />

            <div
                ref={contentRef}
                className="relative w-full max-w-3xl z-10 max-h-[90vh] flex flex-col"
            >
                <AuthCard>
                    {/* Encabezado */}
                    <div className="flex items-center justify-between pb-4 border-b border-line-subtle">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                                <UploadCloud size={20} />
                            </div>
                            <div>
                                <h2 className="text-lg font-bold text-content-primary">
                                    Carga Masiva de Entregas
                                </h2>
                                <p className="text-xs text-content-secondary">
                                    Sube carpetas o grupos enteros de alumnos para análisis bimodal asíncrono.
                                </p>
                            </div>
                        </div>
                        {!isUploading && (
                            <button
                                type="button"
                                onClick={onClose}
                                className="p-1.5 rounded-lg text-content-muted hover:text-content-primary hover:bg-surface-elevated transition-colors"
                            >
                                <X size={18} />
                            </button>
                        )}
                    </div>

                    {/* Cuerpo del Modal */}
                    <div className="space-y-4 pt-4 overflow-y-auto max-h-[calc(80vh-140px)] custom-scrollbar pr-1">
                        {error && (
                            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400 flex items-center gap-2">
                                <AlertCircle size={16} className="shrink-0" />
                                <span>{error}</span>
                            </div>
                        )}

                        {/* Estado en Progreso o Completado */}
                        {isUploading || isCompleted ? (
                            <div className="py-8 space-y-6 text-center">
                                <div className="inline-flex p-4 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                                    {isCompleted ? (
                                        <CheckCircle2 size={40} className="text-emerald-400 animate-in zoom-in" />
                                    ) : (
                                        <Loader2 size={40} className="animate-spin text-cyan-400" />
                                    )}
                                </div>

                                <div className="space-y-1">
                                    <h3 className="text-base font-bold text-content-primary">
                                        {isCompleted
                                            ? "¡Análisis Masivo Completado!"
                                            : `Procesando entrega ${processedCount} de ${totalCount}...`}
                                    </h3>
                                    <p className="text-xs text-content-secondary max-w-md mx-auto">
                                        {isCompleted
                                            ? "Todas las entregas han sido evaluadas e indexadas en la biblioteca con sus dictámenes e indicadores de integridad."
                                            : "Ejecutando inferencia bimodal concurrente (Canal A GraphCodeBERT + Canal B CharCNN) en segundo plano."}
                                    </p>
                                </div>

                                {/* Barra de Progreso */}
                                <div className="max-w-md mx-auto space-y-2">
                                    <div className="h-3 w-full bg-surface-elevated rounded-full overflow-hidden border border-line-subtle p-0.5">
                                        <div
                                            className="h-full bg-gradient-to-r from-cyan-500 via-purple-500 to-emerald-400 rounded-full transition-all duration-300"
                                            style={{ width: `${progressPercent}%` }}
                                        />
                                    </div>
                                    <div className="flex justify-between text-[11px] font-mono text-content-muted">
                                        <span>Progreso: {progressPercent}%</span>
                                        <span>{processedCount} / {totalCount} completados</span>
                                    </div>
                                </div>

                                {isCompleted && (
                                    <div className="pt-4">
                                        <GradientButton onClick={onClose} className="text-xs px-6 py-2.5">
                                            Volver a la Biblioteca
                                        </GradientButton>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <>
                                {/* Selectores de Problema y Curso */}
                                <div className="grid grid-cols-2 gap-3">
                                    <div className="space-y-1.5">
                                        <label className="text-xs font-semibold text-content-secondary flex items-center gap-1.5">
                                            <FileCode2 size={13} className="text-cyan-400" />
                                            Problema de Referencia *
                                        </label>
                                        <select
                                            value={selectedProblemId || ""}
                                            onChange={(e) => setSelectedProblemId(Number(e.target.value))}
                                            className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-line-subtle text-content-primary text-xs focus:outline-none focus:border-cyan-500 transition-colors"
                                        >
                                            {problems.map((p) => (
                                                <option key={p.id} value={p.id}>
                                                    {p.titulo} ({p.lenguaje.toUpperCase()})
                                                </option>
                                            ))}
                                        </select>
                                    </div>

                                    <div className="space-y-1.5">
                                        <label className="text-xs font-semibold text-content-secondary flex items-center gap-1.5">
                                            <Users size={13} className="text-purple-400" />
                                            Asignar a Grupo (Opcional)
                                        </label>
                                        <select
                                            value={selectedGroupId || ""}
                                            onChange={(e) => setSelectedGroupId(e.target.value ? Number(e.target.value) : null)}
                                            className="w-full px-3.5 py-2.5 rounded-xl bg-surface border border-line-subtle text-content-primary text-xs focus:outline-none focus:border-cyan-500 transition-colors"
                                        >
                                            <option value="">Sin grupo (Entrega libre)</option>
                                            {groups.map((g) => (
                                                <option key={g.id} value={g.id}>
                                                    [{g.codigo_grupo}] {g.nombre}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                </div>

                                {/* Zona de Arrastre de Archivos */}
                                <div
                                    onDragOver={(e) => {
                                        e.preventDefault();
                                        setIsDragging(true);
                                    }}
                                    onDragLeave={() => setIsDragging(false)}
                                    onDrop={handleDrop}
                                    className={`p-6 rounded-2xl border-2 border-dashed text-center transition-all duration-200 ${
                                        isDragging
                                            ? "border-cyan-400 bg-cyan-500/10"
                                            : "border-line-subtle hover:border-line-strong bg-surface/50"
                                    }`}
                                >
                                    <input
                                        type="file"
                                        ref={filesInputRef}
                                        multiple
                                        accept=".c,.cpp,.cc,.cxx,.h"
                                        onChange={(e) => e.target.files && handleFilesSelected(e.target.files)}
                                        className="hidden"
                                    />
                                    {/* Input especial para carpeta completa webkitdirectory */}
                                    <input
                                        type="file"
                                        ref={folderInputRef}
                                        // @ts-ignore
                                        webkitdirectory="true"
                                        directory=""
                                        multiple
                                        onChange={(e) => e.target.files && handleFilesSelected(e.target.files)}
                                        className="hidden"
                                    />

                                    <div className="flex flex-col items-center justify-center space-y-3">
                                        <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                                            <UploadCloud size={24} />
                                        </div>
                                        <div>
                                            <p className="text-sm font-semibold text-content-primary">
                                                Arrastra aquí las entregas de tus estudiantes
                                            </p>
                                            <p className="text-xs text-content-muted mt-1">
                                                Archivos de C/C++ (.c, .cpp, .cc). Puedes seleccionar múltiples archivos o carpetas completas.
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-3 pt-1">
                                            <button
                                                type="button"
                                                onClick={() => filesInputRef.current?.click()}
                                                className="px-3.5 py-1.5 rounded-xl bg-surface-elevated border border-line-subtle text-xs font-semibold text-content-secondary hover:text-content-primary transition-colors"
                                            >
                                                Seleccionar Archivos
                                            </button>
                                            <button
                                                type="button"
                                                onClick={() => folderInputRef.current?.click()}
                                                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-xs font-semibold text-purple-400 hover:text-purple-300 transition-colors"
                                            >
                                                <Folder size={13} />
                                                Subir Carpeta de Salón
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                {/* Tabla de Previsualización y Confirmación de Nombres */}
                                {files.length > 0 && (
                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between text-xs">
                                            <span className="font-bold text-content-secondary flex items-center gap-1.5">
                                                <Sparkles size={14} className="text-cyan-400" />
                                                Entregas detectadas ({files.length} archivos)
                                            </span>
                                            <span className="text-[11px] text-content-muted">
                                                Puedes editar los nombres de los alumnos si el archivo no coincide.
                                            </span>
                                        </div>

                                        <div className="max-h-48 overflow-y-auto rounded-xl border border-line-subtle divide-y divide-line-subtle custom-scrollbar bg-surface/30">
                                            {files.map((item, idx) => (
                                                <div
                                                    key={idx}
                                                    className="p-2.5 flex items-center gap-3 hover:bg-surface-elevated/40 transition-colors text-xs"
                                                >
                                                    <FileCode2 size={16} className="text-cyan-400 shrink-0" />
                                                    <div className="w-1/3 truncate text-content-muted font-mono text-[11px]" title={item.filename}>
                                                        {item.filename}
                                                    </div>
                                                    <div className="flex-1 flex items-center gap-1.5">
                                                        <Edit3 size={12} className="text-content-muted" />
                                                        <input
                                                            type="text"
                                                            value={item.authorName}
                                                            onChange={(e) => handleAuthorChange(idx, e.target.value)}
                                                            placeholder="Nombre del alumno"
                                                            className="w-full px-2 py-1 rounded-lg bg-surface border border-line-subtle text-content-primary text-xs focus:outline-none focus:border-cyan-500"
                                                        />
                                                    </div>
                                                    <span className="text-[10px] text-content-muted shrink-0 w-14 text-right">
                                                        {item.sizeFormatted}
                                                    </span>
                                                    <button
                                                        type="button"
                                                        onClick={() => handleRemoveFile(idx)}
                                                        className="p-1 rounded-lg text-content-muted hover:text-rose-400 transition-colors"
                                                        title="Quitar archivo"
                                                    >
                                                        <Trash2 size={14} />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </>
                        )}
                    </div>

                    {/* Acciones */}
                    {!isUploading && !isCompleted && (
                        <div className="flex items-center justify-between pt-4 border-t border-line-subtle mt-4">
                            <span className="text-xs text-content-muted">
                                {files.length > 0 ? `${files.length} entregas listas para encolar.` : "Selecciona archivos para continuar."}
                            </span>
                            <div className="flex items-center gap-3">
                                <button
                                    type="button"
                                    onClick={onClose}
                                    className="px-4 py-2 rounded-xl text-xs font-semibold text-content-secondary hover:text-content-primary transition-colors"
                                >
                                    Cancelar
                                </button>
                                <GradientButton
                                    onClick={handleStartBatch}
                                    disabled={files.length === 0}
                                    className="text-xs px-5 py-2"
                                >
                                    Iniciar Análisis ({files.length})
                                </GradientButton>
                            </div>
                        </div>
                    )}
                </AuthCard>
            </div>
        </div>
    );
}
