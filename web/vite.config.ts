import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

// Aplikácia beží na https://<meno>.github.io/lacne-letenky/ → relatívne cesty
export default defineConfig({
  base: "./",
  plugins: [preact()],
  build: { outDir: "dist", emptyOutDir: true, assetsInlineLimit: 0 },
  server: { port: 5173 },
});
