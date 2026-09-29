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

export function renderSynthwaveTokens(tokens: Token[]): React.ReactNode {
    return tokens.map((token, idx) => {
        switch (token.type) {
            case "keyword":
                return (
                    <span
                        key={idx}
                        className="text-[#ff7edb] font-semibold"
                        style={{ textShadow: "0 0 5px rgba(255, 126, 219, 0.45)" }}
                    >
                        {token.text}
                    </span>
                );
            case "type":
                return (
                    <span
                        key={idx}
                        className="text-[#fe4450] font-medium"
                        style={{ textShadow: "0 0 4px rgba(254, 68, 80, 0.4)" }}
                    >
                        {token.text}
                    </span>
                );
            case "function":
                return (
                    <span
                        key={idx}
                        className="text-[#36f9f6] font-medium"
                        style={{ textShadow: "0 0 5px rgba(54, 249, 246, 0.4)" }}
                    >
                        {token.text}
                    </span>
                );
            case "string":
                return (
                    <span
                        key={idx}
                        className="text-[#fede5d]"
                        style={{ textShadow: "0 0 3px rgba(254, 222, 93, 0.3)" }}
                    >
                        {token.text}
                    </span>
                );
            case "number":
                return (
                    <span
                        key={idx}
                        className="text-[#f97e72]"
                        style={{ textShadow: "0 0 3px rgba(249, 126, 114, 0.3)" }}
                    >
                        {token.text}
                    </span>
                );
            case "preprocessor":
                return (
                    <span
                        key={idx}
                        className="text-[#fede5d] font-bold"
                        style={{ textShadow: "0 0 4px rgba(254, 222, 93, 0.35)" }}
                    >
                        {token.text}
                    </span>
                );
            case "comment":
                return (
                    <span key={idx} className="text-[#848bbd] italic">
                        {token.text}
                    </span>
                );
            case "operator":
                return (
                    <span key={idx} className="text-[#fede5d]/85">
                        {token.text}
                    </span>
                );
            case "plain":
            default:
                return (
                    <span key={idx} className="text-[#e2e8f0]">
                        {token.text}
                    </span>
                );
        }
    });
}

export function SynthwaveLine({ line }: { line: string }) {
    const tokens = useMemo(() => tokenizeLine(line), [line]);
    return <>{renderSynthwaveTokens(tokens)}</>;
}
