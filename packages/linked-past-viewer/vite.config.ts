import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const isStatic = process.env.BUILD_STATIC === "1";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: isStatic ? "/linked-past/viewer/" : "/viewer/",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: isStatic
    ? {}
    : {
        proxy: {
          "/viewer/ws": {
            target: "http://localhost:8000",
            ws: true,
          },
          "/viewer/api": {
            target: "http://localhost:8000",
          },
        },
      },
  build: {
    outDir: isStatic ? "dist-static" : "dist",
    rollupOptions: isStatic
      ? { input: path.resolve(__dirname, "static.html") }
      : undefined,
  },
});
