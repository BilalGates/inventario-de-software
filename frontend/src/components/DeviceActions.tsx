/** Acciones de equipo del menú contextual: las mismas en el Panel, Dispositivos y Departamentos. */
import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { useAction } from "@/lib/hooks";
import { useDepartments } from "@/lib/queries";
import type { DeviceDetail as Device } from "@/lib/types";
import type { MenuEntry } from "./ContextMenu";
import { NotifyDialog } from "./RemoteActionDialogs";
import { DeviceForm, type DeviceFormValues } from "./DeviceForm";
import { Button, Field, Modal, useToast } from "./ui";

export interface DeviceLike {
  id: number;
  name: string;
  serial_number?: string | null;
  status?: string;
  /** El equipo está en Intune (se ofrecen sus acciones remotas). */
  intune?: boolean;
  /** Tiene software no autorizado (se ofrece avisar al usuario). */
  unauthorized?: boolean;
}

const INVALIDATE = [["devices"], ["dashboard"], ["departments"]];

export function useDeviceActions() {
  const nav = useNavigate();
  const can = useCan();
  const toast = useToast();
  const depts = useDepartments().data?.items.filter((d) => d.active) ?? [];
  const [editing, setEditing] = useState<Device | null>(null);
  const [owner, setOwner] = useState<{ device: DeviceLike; upn: string } | null>(null);
  const [retiring, setRetiring] = useState<{ devices: DeviceLike[]; reactivate: boolean; reason: string } | null>(null);
  const [notifying, setNotifying] = useState<number[] | null>(null);

  const move = useAction(({ ids, department_id }: { ids: number[]; department_id: number | null }) =>
    api.send<{ moved: number }>("POST", "/devices/bulk-assign", { device_ids: ids, department_id, reason: "Movido desde el menú de acciones" }),
  { success: (r) => `${r.moved} ${r.moved === 1 ? "equipo movido" : "equipos movidos"}`, invalidate: INVALIDATE });
  const save = useAction(({ id, v }: { id: number; v: DeviceFormValues }) => api.send("PATCH", `/devices/${id}`, v),
    { success: "Cambios guardados", invalidate: [...INVALIDATE, ["device"]], onSuccess: () => { setEditing(null); setOwner(null); } });
  const intune = useAction(({ id, action }: { id: number; action: string }) =>
    api.send<{ message: string }>("POST", `/devices/${id}/intune-actions`, { action }), { success: (r) => r.message });
  const check = useAction((id: number) => api.get(`/devices/${id}/compliance`),
    { success: "Cumplimiento comprobado en Intune", invalidate: INVALIDATE });
  const retire = useAction(async (r: { devices: DeviceLike[]; reactivate: boolean; reason: string }) => {
    for (const d of r.devices) await api.send("POST", `/devices/${d.id}/${r.reactivate ? "reactivate" : "retire"}`, { reason: r.reason });
    return r.devices.length;
  }, { success: (n) => (n === 1 ? "Estado actualizado" : `${n} equipos actualizados`), invalidate: INVALIDATE,
    onSuccess: () => setRetiring(null) });

  const copy = (text: string, what: string) => {
    navigator.clipboard?.writeText(text).then(() => toast("ok", `${what} copiado`), () => toast("danger", "No se pudo copiar"));
  };
  const openEdit = async (id: number) => {
    try { setEditing(await api.get<Device>(`/devices/${id}`)); } catch (e) { toast("danger", (e as Error).message); }
  };

  /** Entradas del menú para un equipo (o para la selección, si hay varios). */
  const entries = (device: DeviceLike, selection: DeviceLike[] = [device]): MenuEntry[] => {
    const many = selection.length > 1;
    const ids = selection.map((d) => d.id);
    const retired = device.status === "retired";
    const moveTo: MenuEntry[] = [
      ...depts.map((d) => ({ label: d.name, onSelect: () => move.mutate({ ids, department_id: d.id }) })),
      "separator",
      { label: "Sin departamento", onSelect: () => move.mutate({ ids, department_id: null }) },
    ];
    if (many) {
      return [
        ...(can.write ? [{ label: `Mover ${selection.length} equipos`, submenu: moveTo } as MenuEntry] : []),
        { label: "Copiar nombres", onSelect: () => copy(selection.map((d) => d.name).join("\n"), "Nombres") },
        ...(can.write && selection.some((d) => d.unauthorized) ? [{ label: "Avisar a sus usuarios del software no autorizado…",
          onSelect: () => setNotifying(selection.filter((d) => d.unauthorized).map((d) => d.id)) } as MenuEntry] : []),
        ...(can.write ? ["separator" as const, { label: `Dar de baja ${selection.length} equipos…`, danger: true,
          onSelect: () => setRetiring({ devices: selection.filter((d) => d.status !== "retired"), reactivate: false, reason: "" }) }] : []),
      ];
    }
    const out: MenuEntry[] = [
      { label: "Abrir ficha", hint: "Intro", onSelect: () => nav(`/dispositivos/${device.id}`) },
      { label: "Abrir en pestaña nueva", onSelect: () => window.open(`/dispositivos/${device.id}`, "_blank", "noopener") },
      { label: "Ver software instalado", onSelect: () => nav(`/dispositivos/${device.id}?tab=software`) },
    ];
    if (can.write && !retired) {
      out.push("separator",
        { label: "Editar…", onSelect: () => openEdit(device.id) },
        { label: "Mover a departamento", submenu: moveTo },
        { label: "Asignar usuario…", onSelect: () => setOwner({ device, upn: "" }) });
      if (device.unauthorized) {
        out.push({ label: "Avisar al usuario de su software no autorizado…", onSelect: () => setNotifying([device.id]) });
      }
      if (device.intune) {
        out.push({ label: "Intune", submenu: [
          { label: "Sincronizar equipo", onSelect: () => intune.mutate({ id: device.id, action: "sync" }) },
          { label: "Actualizar firmas de Defender", onSelect: () => intune.mutate({ id: device.id, action: "defender_signatures" }) },
          { label: "Análisis rápido de Defender", onSelect: () => intune.mutate({ id: device.id, action: "defender_scan" }) },
          "separator",
          { label: "Comprobar cumplimiento", onSelect: () => check.mutate(device.id) },
        ] });
      }
    }
    out.push("separator",
      { label: "Copiar nombre", onSelect: () => copy(device.name, "Nombre") },
      { label: "Copiar n.º de serie", disabled: !device.serial_number, onSelect: () => copy(device.serial_number ?? "", "Número de serie") },
      { label: "Exportar este equipo", onSelect: () => api.download("/devices/export", { format: "xlsx", q: device.name })
        .catch((e: Error) => toast("danger", e.message)) });
    if (can.write) {
      out.push("separator", retired
        ? { label: "Reactivar…", onSelect: () => setRetiring({ devices: [device], reactivate: true, reason: "" }) }
        : { label: "Dar de baja…", danger: true, onSelect: () => setRetiring({ devices: [device], reactivate: false, reason: "" }) });
    }
    return out;
  };

  const dialogs: ReactNode = (
    <>
      {notifying && <NotifyDialog scope={{ device_ids: notifying }} onClose={() => setNotifying(null)} />}
      {editing && (
        <DeviceForm open onClose={() => setEditing(null)} initial={editing} title={`Editar ${editing.name}`} busy={save.isPending}
          onSubmit={(v) => save.mutate({ id: editing.id, v })} />
      )}
      {owner && (
        <Modal open onClose={() => setOwner(null)} title={`Asignar usuario a ${owner.device.name}`} footer={<>
          <Button onClick={() => setOwner(null)}>Cancelar</Button>
          <Button variant="primary" loading={save.isPending} disabled={!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(owner.upn)}
            onClick={() => save.mutate({ id: owner.device.id, v: { primary_user_upn: owner.upn.trim() } })}>Asignar</Button>
        </>}>
          <Field label="Usuario principal (UPN)" hint="Si Intune informa otro usuario, prevalece el indicado aquí.">
            {(id) => <input id={id} type="email" className="field" autoFocus placeholder="nombre@asserta.es" value={owner.upn}
              onChange={(e) => setOwner({ ...owner, upn: e.target.value })} />}
          </Field>
        </Modal>
      )}
      {retiring && (
        <Modal open onClose={() => setRetiring(null)}
          title={retiring.reactivate ? "Reactivar dispositivo"
            : retiring.devices.length === 1 ? `Dar de baja ${retiring.devices[0].name}` : `Dar de baja ${retiring.devices.length} equipos`}
          footer={<>
            <Button onClick={() => setRetiring(null)}>Cancelar</Button>
            <Button variant={retiring.reactivate ? "primary" : "danger"} loading={retire.isPending}
              disabled={retiring.reason.trim().length < 3} onClick={() => retire.mutate(retiring)}>
              {retiring.reactivate ? "Reactivar" : "Dar de baja"}</Button>
          </>}>
          <Field label="Motivo (obligatorio)">
            {(id) => <input id={id} className="field" autoFocus value={retiring.reason}
              onChange={(e) => setRetiring({ ...retiring, reason: e.target.value })} />}
          </Field>
        </Modal>
      )}
    </>
  );

  return { entries, dialogs };
}
