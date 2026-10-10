/**
 * @file filename_parser.ts
 * @description Extracción heurística de nombres de alumnos y matrículas a partir
 * de nombres de archivos de código fuente (.c, .cpp, .cc) entregados en prácticas.
 */

export interface ParsedStudentFile {
    file: File;
    authorName: string;
    filename: string;
    studentId?: string;
    sizeFormatted: string;
}

export function formatFileSize(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function parseStudentFilename(file: File): ParsedStudentFile {
    const filename = file.name;
    // Remover extensión
    const cleanName = filename.replace(/\.(c|cpp|cc|cxx|h|hpp)$/i, "");

    // Separar por guiones bajos, medios o espacios
    const rawTokens = cleanName.split(/[-_\s]+/).map((t) => t.trim()).filter(Boolean);

    let studentId: string | undefined = undefined;
    const nameTokens: string[] = [];

    for (const token of rawTokens) {
        // Detección de boleta / matrícula (generalmente 7 a 10 dígitos o empieza con PE/AL)
        if (/^\d{7,11}$/.test(token) || /^(pe|al|es|boleta)\d+/i.test(token)) {
            studentId = token;
        } else if (/^(practica|tarea|lab|asignacion|p\d+|t\d+|v\d+|final|entrega)\d*$/i.test(token)) {
            // Ignorar palabras que describen el trabajo
            continue;
        } else {
            // Capitalizar palabra
            const capitalized = token.charAt(0).toUpperCase() + token.slice(1).toLowerCase();
            nameTokens.push(capitalized);
        }
    }

    const authorName = nameTokens.length > 0 ? nameTokens.join(" ") : cleanName;

    return {
        file,
        authorName,
        filename,
        studentId,
        sizeFormatted: formatFileSize(file.size),
    };
}
