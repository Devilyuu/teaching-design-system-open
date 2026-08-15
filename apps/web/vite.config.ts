import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

import { resolveBasePath } from "./src/buildConfig";

export default defineConfig(({ command }) => ({
  base: resolveBasePath(command, process.env.VITE_BASE_PATH),
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts"
  }
}));
