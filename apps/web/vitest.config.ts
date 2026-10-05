import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, ".") },
  },
  test: {
    environment: "jsdom",
    globals: true,
    // Forked workers time out on slow/synced (OneDrive) folders on Windows; threads are reliable.
    pool: "threads",
    maxWorkers: 2,
    testTimeout: 20_000,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    css: false,
  },
});
