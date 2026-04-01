import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/viewer/",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
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
    outDir: "dist",
  },
});
