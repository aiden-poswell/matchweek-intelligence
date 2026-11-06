import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // App.test.tsx renders the full 760-fixture dataset through the real app (not a
    // trimmed fixture), so under full-suite load (multiple files, no DOM
    // virtualization on a 380-row list) a render + effect flush can genuinely take
    // longer than the 5s default — this is real render cost, not a hung test.
    testTimeout: 15000,
  },
});
