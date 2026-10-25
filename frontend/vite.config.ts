import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En dev, l'API Django est servie sous la même origine via le proxy : cookie de session et CSRF fonctionnent tels quels.
const backend = process.env.SOLUGATION_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    // Dans Docker (Colima), les événements fichiers ne traversent pas le montage : scrutation périodique.
    watch: process.env.SOLUGATION_SCRUTATION ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
    },
  },
});
