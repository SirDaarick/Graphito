/**
 * @file SynthwaveHighlighter.tsx
 * @description Resaltador sintáctico y léxico de alto rendimiento inspirado en el tema "Synthwave '84" de VS Code.
 * Implementa un tokenizador determinista de paso único sin dependencias pesadas de runtime para C/C++,
 * optimizado para baja latencia en renderizado simultáneo de miles de líneas de código en vistas Diff.
 */

import React, { useMemo } from "react";

interface SynthwaveHighlighterProps {
    code: string;
    language?: "c" | "cpp" | string;
    className?: string;
}

// C / C++ Keywords and Preprocessor tokens
const KEYWORDS = new Set([
    "auto", "break", "case", "char", "const", "continue", "default", "do",
    "double", "else", "enum", "extern", "float", "for", "goto", "if",
    "inline", "int", "long", "register", "restrict", "return", "short",
    "signed", "sizeof", "static", "struct", "switch", "typedef", "union",
    "unsigned", "void", "volatile", "while",
    // C++ specific
    "class", "namespace", "using", "template", "typename", "public", "private",
    "protected", "virtual", "override", "constexpr", "nullptr", "new", "delete",
    "try", "catch", "throw", "bool", "true", "false", "friend", "explicit"
]);

const TYPES = new Set([
    "string", "vector", "map", "set", "queue", "stack", "deque", "pair",
    "size_t", "int8_t", "int16_t", "int32_t", "int64_t", "uint8_t", "uint16_t",
    "uint32_t", "uint64_t", "FILE", "NULL", "std"
]);

interface Token {
    text: string;
    type: "keyword" | "type" | "function" | "string" | "number" | "comment" | "preprocessor" | "operator" | "plain";
}

export function tokenizeLine(line: string): Token[] {
    const tokens: Token[] = [];
    let i = 0;
    const len = line.length;

    while (i < len) {
        // Line comments //
        if (line.slice(i, i + 2) === "//") {
            tokens.push({ text: line.slice(i), type: "comment" });
            break;
        }

        // Preprocessor directives (#include, #define, etc.)
        if (line[i] === "#") {
            let j = i + 1;
            while (j < len && /[a-zA-Z_]/.test(line[j])) j++;
            tokens.push({ text: line.slice(i, j), type: "preprocessor" });
            i = j;
            continue;
        }

        // Strings "..."
        if (line[i] === '"') {
            let j = i + 1;
            while (j < len && line[j] !== '"') {
                if (line[j] === "\\" && j + 1 < len) j += 2;
                else j++;
            }
            if (j < len && line[j] === '"') j++;
            tokens.push({ text: line.slice(i, j), type: "string" });
            i = j;
            continue;
        }

        // Character literals '...'
        if (line[i] === "'") {
            let j = i + 1;
            while (j < len && line[j] !== "'") {
                if (line[j] === "\\" && j + 1 < len) j += 2;
                else j++;
            }
            if (j < len && line[j] === "'") j++;
            tokens.push({ text: line.slice(i, j), type: "string" });
            i = j;
            continue;
        }

        // Numbers (hex, float, dec)
        if (/[0-9]/.test(line[i]) && (i === 0 || /[^a-zA-Z0-9_]/.test(line[i - 1]))) {
            let j = i;
            if (line.slice(j, j + 2) === "0x" || line.slice(j, j + 2) === "0X") {
                j += 2;
                while (j < len && /[0-9a-fA-F]/.test(line[j])) j++;
            } else {
                while (j < len && /[0-9.]/.test(line[j])) j++;
            }
            tokens.push({ text: line.slice(i, j), type: "number" });
            i = j;
            continue;
        }

        // Identifiers / Keywords / Functions
        if (/[a-zA-Z_]/.test(line[i])) {
            let j = i;
            while (j < len && /[a-zA-Z0-9_]/.test(line[j])) j++;
            const word = line.slice(i, j);

            // Peek next non-space char to check if it's a function call
            let k = j;
            while (k < len && (line[k] === " " || line[k] === "\t")) k++;
            const isFunction = k < len && line[k] === "(";

            if (KEYWORDS.has(word)) {
                tokens.push({ text: word, type: "keyword" });
            } else if (TYPES.has(word)) {
                tokens.push({ text: word, type: "type" });
            } else if (isFunction) {
                tokens.push({ text: word, type: "function" });
            } else {
                tokens.push({ text: word, type: "plain" });
            }
            i = j;
            continue;
        }

        // Operators & delimiters
        if (/[+\-*\/%=<>!&|^~?:;.,(){}\[\]]/.test(line[i])) {
            tokens.push({ text: line[i], type: "operator" });
            i++;
            continue;
        }

        // Whitespace and other characters
        tokens.push({ text: line[i], type: "plain" });
        i++;
    }

    return tokens;
}

/** Light theme: deep, readable hues on white. Dark theme: the Synthwave '84 neon palette. */
const TOKEN_CLASS: Record<Token["type"], string> = {
    keyword: "text-fuchsia-700 font-semibold dark:text-[#ff7edb] dark:[text-shadow:0_0_5px_rgba(255,126,219,0.45)]",
    type: "text-rose-700 font-medium dark:text-[#fe4450] dark:[text-shadow:0_0_4px_rgba(254,68,80,0.4)]",
    function: "text-cyan-800 font-medium dark:text-[#36f9f6] dark:[text-shadow:0_0_5px_rgba(54,249,246,0.4)]",
    string: "text-amber-800 dark:text-[#fede5d] dark:[text-shadow:0_0_3px_rgba(254,222,93,0.3)]",
    number: "text-orange-700 dark:text-[#f97e72] dark:[text-shadow:0_0_3px_rgba(249,126,114,0.3)]",
    preprocessor: "text-amber-800 font-bold dark:text-[#fede5d] dark:[text-shadow:0_0_4px_rgba(254,222,93,0.35)]",
    comment: "text-slate-500 italic dark:text-[#848bbd]",
    operator: "text-slate-600 dark:text-[#fede5d]/85",
    plain: "text-slate-800 dark:text-[#e2e8f0]",
};

export function renderSynthwaveTokens(tokens: Token[]): React.ReactNode {
    return tokens.map((token, idx) => (
        <span key={idx} className={TOKEN_CLASS[token.type]}>
            {token.text}
        </span>
    ));
}
export function SynthwaveLine({ line }: { line: string }) {
    const tokens = useMemo(() => tokenizeLine(line), [line]);
    return <>{renderSynthwaveTokens(tokens)}</>;
}
