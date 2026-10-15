import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "@/App";
import { ToastProvider } from "@/components/ui";
import { TestAuthProvider } from "@/lib/auth";
import type { Me } from "@/lib/types";

const responses: Record<string, unknown> = {
  "/api/alerts": { total: 0, items: [] },
  "/api/devices": { total: 1, items: [{ id: 7, uid: "u", name: "PC-007", hostname: "PC-007", serial_number: "S1",
    manufacturer: null, model: null, os_name: null, os_version: null, device_type_id: null, device_type: null,
    status: "active", freshness: "current", department_id: null, department: null, primary_user_id: null,
    primary_user: null, primary_user_upn: null, location: null, compliance_state: null, encrypted: null,
    ram_bytes: null, storage_total_bytes: null, last_seen_at: null, last_seen_source: null, source_last_sync_at: null,
    software_count: 4, sources: ["intune"] }] },
  "/api/departments": { items: [], unassigned_devices: 1 },
  "/api/devices/meta/types": [],
};

function mockFetch() {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    const path = url.split("?")[0];
    const body = responses[path];
    return new Response(JSON.stringify(body ?? { detail: "no mock" }), { status: body ? 200 : 404,
      headers: { "Content-Type": "application/json" } });
  }));
}

function renderAt(path: string, role: Me["role"]) {
  const me: Me = { upn: "x@test", name: "X", role, permissions: { read: true, write: role !== "auditor", admin: role === "admin" } };
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[path]}>
        <ToastProvider><TestAuthProvider me={me}><App /></TestAuthProvider></ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("navegación y permisos", () => {
  beforeEach(mockFetch);
  afterEach(() => vi.unstubAllGlobals());

  it("un técnico ve la lista y puede crear dispositivos", async () => {
    renderAt("/dispositivos", "technician");
    expect(await screen.findByRole("link", { name: "PC-007" })).toHaveAttribute("href", "/dispositivos/7");
    expect(screen.getByRole("button", { name: /Nuevo dispositivo/ })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Principal" })).toBeInTheDocument();
  });

  it("un auditor no ve acciones de modificación", async () => {
    renderAt("/dispositivos", "auditor");
    await screen.findByRole("link", { name: "PC-007" });
    expect(screen.queryByRole("button", { name: /Nuevo dispositivo/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Seleccionar todos" })).not.toBeInTheDocument();
  });

  it("ruta desconocida muestra página no encontrada", async () => {
    renderAt("/no-existe", "admin");
    expect(await screen.findByText("Página no encontrada")).toBeInTheDocument();
  });
});
