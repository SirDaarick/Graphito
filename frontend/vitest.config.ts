import { defineConfig } from "vitest/config";

// Unit tests for pure helpers in src/lib; no DOM environment is needed.
export default defineConfig({
    test: {
        environment: "node",
        include: ["src/**/*.test.ts"],
    },
});
