import { defineConfig } from "@playwright/test";
import { resolve } from "node:path";

const python = process.env.E2E_PYTHON ? resolve(process.env.E2E_PYTHON) : "python";
const server = resolve("../backend/tests/e2e_server.py");

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: "http://127.0.0.1:8765", trace: "retain-on-failure", locale: "es-ES" },
  webServer: {
    // Requiere el frontend compilado (npm run build): la API sirve la SPA desde dist/.
    command: `"${python}" "${server}" --port 8765`,
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
