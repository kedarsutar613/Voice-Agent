import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      proxy: {
        "/api": {
          target: env.API_PROXY_TARGET || "http://127.0.0.1:8000",
          ws: true,
        },
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            charts: ["recharts"],
            react: ["react", "react-dom", "react-router-dom"],
          },
        },
      },
    },
    test: { environment: "jsdom", setupFiles: ["./src/test-setup.js"] },
  };
});
