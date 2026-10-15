import { expect, test } from "@playwright/test";

const PANDA = [
  "Nombre\tEditor\tFecha de instalación\tTamaño\tVersión",
  "AnyDesk\tAnyDesk Software GmbH\t10/03/2026\t2 MB\t9.0.10",
  "Google Chrome\tGoogle LLC\t01/02/2026\t100 MB\t129.0.1",
].join("\n");

test.describe.configure({ mode: "serial" });

test("departamento → dispositivo → importación Panda → software → autorización → inventario mensual", async ({ page }) => {
  // 1. Crear departamento
  await page.goto("/departamentos");
  await page.getByRole("button", { name: "Nuevo departamento" }).click();
  await page.getByRole("dialog").getByLabel("Nombre").fill("Laboratorio E2E");
  await page.getByRole("button", { name: "Guardar" }).click();
  await expect(page.getByRole("heading", { name: "Laboratorio E2E" })).toBeVisible();

  // 2. Alta manual de un dispositivo asignado al departamento
  await page.goto("/dispositivos");
  await page.getByRole("button", { name: "Nuevo dispositivo" }).click();
  await page.getByRole("dialog").getByLabel("Nombre del equipo").fill("E2E-PC-01");
  await page.getByRole("dialog").getByLabel("Número de serie").fill("E2ESERIAL01");
  await page.getByRole("dialog").getByLabel("Departamento").selectOption({ label: "Laboratorio E2E" });
  await page.getByRole("button", { name: "Guardar" }).click();
  await expect(page.getByRole("heading", { name: "E2E-PC-01" })).toBeVisible();
  const deviceUrl = page.url();

  // 3. Importar una exportación de Panda para ese equipo; la procesa el worker real
  await page.getByRole("button", { name: "Importar Panda" }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: "export.txt", mimeType: "text/plain", buffer: Buffer.from(PANDA) });
  await page.getByRole("button", { name: "Importar", exact: true }).click();
  await expect(page).toHaveURL(/sincronizacion/);
  await expect(page.getByRole("cell", { name: "Completada" }).first()).toBeVisible({ timeout: 20_000 });

  // 4. El software aparece en la ficha, sin autorizar automáticamente
  await page.goto(deviceUrl);
  await page.getByRole("tab", { name: "Software" }).click();
  await expect(page.getByRole("link", { name: "AnyDesk" })).toBeVisible();
  await expect(page.getByText("No clasificado").first()).toBeVisible();

  // 5. Prohibir AnyDesk globalmente → alerta crítica
  await page.getByRole("link", { name: "AnyDesk" }).click();
  await page.getByRole("button", { name: "Autorización" }).click();
  await page.getByRole("dialog").getByLabel("Estado").selectOption("unauthorized");
  await page.getByRole("button", { name: "Registrar" }).click();
  await expect(page.getByText("Autorización registrada")).toBeVisible();
  await page.goto("/auditoria?tab=alertas");
  await expect(page.getByText("Software no autorizado: AnyDesk en E2E-PC-01")).toBeVisible();

  // 6. Generar y revisar el inventario del mes (incompleto: Intune no sincronizó)
  await page.goto("/auditoria");
  await page.getByRole("button", { name: "Generar inventario" }).click();
  await expect(page.getByText("Incompleta").first()).toBeVisible();
  await page.getByRole("button", { name: "Revisar" }).click();
  await expect(page.getByRole("button", { name: "Aprobar" })).toBeDisabled();
  await page.getByRole("dialog").getByLabel(/Acepto aprobarlo incompleto/).check();
  await page.getByRole("dialog").getByLabel("Notas de revisión").fill("Intune pendiente de credenciales");
  await page.getByRole("button", { name: "Aprobar" }).click();
  await expect(page.getByText("Aprobado")).toBeVisible();

  // 7. Trazabilidad: el registro de auditoría es íntegro
  await page.getByRole("tab", { name: "Registro de auditoría" }).click();
  await page.getByRole("button", { name: "Verificar integridad" }).click();
  await expect(page.getByText(/Cadena íntegra/)).toBeVisible();
});

test("movimiento masivo de dispositivos conserva el historial", async ({ page }) => {
  await page.goto("/departamentos");
  await page.getByRole("button", { name: "Nuevo departamento" }).click();
  await page.getByRole("dialog").getByLabel("Nombre").fill("Destino E2E");
  await page.getByRole("button", { name: "Guardar" }).click();
  await expect(page.getByText("Departamento creado")).toBeVisible();

  await page.goto("/dispositivos?q=E2E-PC");
  await page.getByRole("checkbox", { name: "Seleccionar todos" }).check();
  await page.getByRole("button", { name: "Mover" }).click();
  await page.getByRole("dialog").getByLabel("Departamento de destino").selectOption({ label: "Destino E2E" });
  await page.getByRole("dialog").getByLabel("Motivo").fill("Reorganización E2E");
  await page.getByRole("button", { name: "Mover", exact: true }).last().click();
  await expect(page.getByText("1 dispositivos movidos")).toBeVisible();

  await page.getByRole("link", { name: "E2E-PC-01" }).click();
  await page.getByRole("tab", { name: "Asignaciones" }).click();
  await expect(page.getByRole("cell", { name: "Destino E2E" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Laboratorio E2E" })).toBeVisible();
  await expect(page.getByText("Vigente")).toBeVisible();
});

test("la sincronización de Intune sin credenciales se bloquea con un mensaje claro", async ({ page }) => {
  await page.goto("/sincronizacion");
  await expect(page.getByText("Sin credenciales")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sincronizar ahora" })).toBeDisabled();
});
