import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { EmptyState, Spinner } from "./components/ui";
import { Dashboard } from "./pages/Dashboard";

const Devices = lazy(() => import("./pages/Devices"));
const DeviceDetail = lazy(() => import("./pages/DeviceDetail"));
const Software = lazy(() => import("./pages/Software"));
const SoftwareDetail = lazy(() => import("./pages/SoftwareDetail"));
const Departments = lazy(() => import("./pages/Departments"));
const DepartmentDetail = lazy(() => import("./pages/DepartmentDetail"));
const Audit = lazy(() => import("./pages/Audit"));
const Sync = lazy(() => import("./pages/Sync"));
const SettingsPage = lazy(() => import("./pages/Settings"));

export function App() {
  return (
    <AppShell>
      <Suspense fallback={<Spinner />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dispositivos" element={<Devices />} />
          <Route path="/dispositivos/:id" element={<DeviceDetail />} />
          <Route path="/software" element={<Software />} />
          <Route path="/software/:id" element={<SoftwareDetail />} />
          <Route path="/departamentos" element={<Departments />} />
          <Route path="/departamentos/:id" element={<DepartmentDetail />} />
          <Route path="/auditoria" element={<Audit />} />
          <Route path="/sincronizacion" element={<Sync />} />
          <Route path="/configuracion" element={<SettingsPage />} />
          <Route path="*" element={<EmptyState title="Página no encontrada"><Link className="text-accent" to="/">Volver al panel</Link></EmptyState>} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
