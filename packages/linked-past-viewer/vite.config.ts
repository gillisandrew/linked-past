import path from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const isStatic = process.env.BUILD_STATIC === "1";

/**
 * In static dev mode, rewrite HTML requests to serve static/index.html
 * instead of the root index.html (which loads the live entrypoint).
 */
function staticDevEntry(): Plugin {
  return {
    name: "static-dev-entry",
    configureServer(server) {
      return () => {
        server.middlewares.use((req, _res, next) => {
          const url = req.url ?? "";
          if (
            req.headers.accept?.includes("text/html") &&
            !url.startsWith("/@") &&
            !url.startsWith("/src/") &&
            !url.startsWith("/node_modules/")
          ) {
            req.url = "/static/index.html";
          }
          next();
        });
      };
    },
  };
}

export default defineConfig(({ command }) => {
  const isDev = command === "serve";

  return {
    plugins: [react(), tailwindcss(), ...(isStatic && isDev ? [staticDevEntry()] : [])],
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
        ? { input: path.resolve(__dirname, "static/index.html") }
        : undefined,
    },
  };
});
