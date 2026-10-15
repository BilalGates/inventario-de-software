import { useState } from "react";
import { DEVICE_STATUS_LABEL } from "@/lib/format";
import { useDepartments, useDeviceTypes } from "@/lib/queries";
import type { DeviceDetail } from "@/lib/types";
import { Button, Field, Modal } from "./ui";

export interface DeviceFormValues {
  hostname?: string | null;
  serial_number?: string | null;
  manufacturer?: string | null;
  model?: string | null;
  os_name?: string | null;
  os_version?: string | null;
  device_type_id?: number | null;
  status?: string;
  location?: string | null;
  notes?: string | null;
  department_id?: number | null;
  primary_user_upn?: string | null;
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function DeviceForm({ open, onClose, initial, onSubmit, busy, title }: {
  open: boolean; onClose: () => void; initial?: Partial<DeviceDetail>; busy?: boolean; title: string;
  onSubmit: (v: DeviceFormValues) => void;
}) {
  const depts = useDepartments().data?.items.filter((d) => d.active || d.id === initial?.department_id) ?? [];
  const types = useDeviceTypes().data ?? [];
  const [v, setV] = useState<DeviceFormValues>(() => ({
    hostname: initial?.hostname ?? "", serial_number: initial?.serial_number ?? "",
    manufacturer: initial?.manufacturer ?? "", model: initial?.model ?? "", os_name: initial?.os_name ?? "",
    os_version: initial?.os_version ?? "", device_type_id: initial?.device_type_id ?? null,
    status: initial?.status && initial.status !== "retired" ? initial.status : "active",
    location: initial?.location ?? "", notes: initial?.notes ?? "", department_id: initial?.department_id ?? null,
    primary_user_upn: initial?.primary_user_upn ?? "",
  }));
  const [touched, setTouched] = useState(false);
  const set = (k: keyof DeviceFormValues) => (e: { target: { value: string } }) =>
    setV((p) => ({ ...p, [k]: e.target.value }));
  const identityError = !v.hostname?.trim() && !v.serial_number?.trim() ? "Indique el nombre o el número de serie" : null;
  const upnError = v.primary_user_upn && !EMAIL.test(v.primary_user_upn) ? "Formato usuario@dominio" : null;

  const submit = () => {
    setTouched(true);
    if (identityError || upnError) return;
    const clean = Object.fromEntries(Object.entries(v).map(([k, val]) =>
      [k, typeof val === "string" ? val.trim() || null : val])) as DeviceFormValues;
    clean.status = v.status;
    onSubmit(clean);
  };

  const text = (k: keyof DeviceFormValues, label: string, hint?: string) => (
    <Field label={label} hint={hint} error={k === "hostname" && touched ? identityError : null}>
      {(id) => <input id={id} className="field" value={(v[k] as string) ?? ""} onChange={set(k)} />}
    </Field>
  );

  return (
    <Modal open={open} onClose={onClose} title={title} wide footer={<>
      <Button onClick={onClose}>Cancelar</Button>
      <Button variant="primary" loading={busy} onClick={submit}>Guardar</Button>
    </>}>
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        {text("hostname", "Nombre del equipo")}
        {text("serial_number", "Número de serie")}
        <Field label="Tipo">
          {(id) => (
            <select id={id} className="field" value={v.device_type_id ?? ""}
              onChange={(e) => setV((p) => ({ ...p, device_type_id: e.target.value ? Number(e.target.value) : null }))}>
              <option value="">Sin clasificar</option>
              {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          )}
        </Field>
        <Field label="Estado">
          {(id) => (
            <select id={id} className="field" value={v.status} onChange={set("status")}>
              {["active", "in_stock", "repair", "lost"].map((s) => <option key={s} value={s}>{DEVICE_STATUS_LABEL[s]}</option>)}
            </select>
          )}
        </Field>
        <Field label="Departamento">
          {(id) => (
            <select id={id} className="field" value={v.department_id ?? ""}
              onChange={(e) => setV((p) => ({ ...p, department_id: e.target.value ? Number(e.target.value) : null }))}>
              <option value="">Sin departamento</option>
              {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          )}
        </Field>
        <Field label="Usuario principal (UPN)" error={touched ? upnError : null}
          hint="Si Intune informa otro usuario, prevalece el indicado aquí.">
          {(id) => <input id={id} type="email" className="field" placeholder="nombre@asserta.es"
            value={v.primary_user_upn ?? ""} onChange={set("primary_user_upn")} />}
        </Field>
        {text("manufacturer", "Fabricante")}
        {text("model", "Modelo")}
        {text("os_name", "Sistema operativo")}
        {text("os_version", "Versión del SO")}
        <div className="sm:col-span-2">{text("location", "Ubicación")}</div>
        <div className="sm:col-span-2">
          <Field label="Observaciones administrativas">
            {(id) => <textarea id={id} rows={3} className="field" value={v.notes ?? ""} onChange={set("notes")} />}
          </Field>
        </div>
        <button type="submit" hidden />
      </form>
    </Modal>
  );
}
