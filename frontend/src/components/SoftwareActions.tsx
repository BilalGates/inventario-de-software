/** Clasificación de software con «Deshacer» y el menú de acciones de un producto. */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useCan } from "@/lib/auth";
import { CATEGORY_LABEL } from "@/lib/format";
import type { MenuEntry } from "./ContextMenu";
import { StatusDot, authDot } from "./kit";
import { NotifyDialog, UninstallDialog } from "./RemoteActionDialogs";
import { Button, Field, Modal, useToast } from "./ui";

export const POLICY_LABEL: Record<string, string> = {
  authorized: "Autorizado", conditional: "Con condiciones", unauthorized: "No autorizado",
  pending_review: "Por decidir", unclassified: "Por decidir", exception: "Excepción",
};

export interface ProductLike { id: number; name: string; status: string; devices?: number }

const KEYS = [["software"], ["dashboard"], ["alerts"], ["alerts-count"], ["product"]];

/** Cambia la política de uno o varios productos; el aviso ofrece deshacer (vuelve al estado anterior de cada uno). */
export function useClassify() {
  const qc = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const refresh = () => KEYS.forEach((k) => qc.invalidateQueries({ queryKey: k }));
  const send = (ids: number[], status: string, reason: string) =>
    api.send<{ updated: number }>("POST", "/software/bulk-update", { product_ids: ids, authorization_status: status, reason });

  const classify = async (products: ProductLike[], status: string) => {
    if (!products.length) return;
    setBusy(true);
    try {
      await send(products.map((p) => p.id), status, "Clasificación desde el menú de acciones");
      refresh();
      const what = products.length === 1 ? products[0].name : `${products.length} aplicaciones`;
      toast("ok", `${what} → ${POLICY_LABEL[status]}`, {
        label: "Deshacer",
        run: async () => {
          // Agrupa por estado anterior para restaurar cada producto como estaba.
          const before = new Map<string, number[]>();
          products.forEach((p) => before.set(p.status, [...(before.get(p.status) ?? []), p.id]));
          try {
            for (const [prev, ids] of before) await send(ids, prev, "Deshacer clasificación");
            refresh();
            toast("ok", "Clasificación deshecha");
          } catch (e) {
            toast("danger", (e as Error).message);
          }
        },
      });
    } catch (e) {
      toast("danger", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return { classify, busy };
}

/** Menú contextual de un producto del catálogo. */
export function useProductActions() {
  const nav = useNavigate();
  const can = useCan();
  const toast = useToast();
  const qc = useQueryClient();
  const { classify } = useClassify();
  const [merging, setMerging] = useState<{ product: ProductLike; target: string; reason: string } | null>(null);
  const [mergeBusy, setMergeBusy] = useState(false);
  const [notifying, setNotifying] = useState<number | null>(null);
  const [uninstalling, setUninstalling] = useState<number | null>(null);

  const patch = async (ids: number[], body: Record<string, unknown>, ok: string) => {
    try {
      await api.send("POST", "/software/bulk-update", { product_ids: ids, ...body });
      KEYS.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      toast("ok", ok);
    } catch (e) {
      toast("danger", (e as Error).message);
    }
  };

  const entries = (p: ProductLike, selection: ProductLike[] = [p]): MenuEntry[] => {
    const many = selection.length > 1;
    const ids = selection.map((x) => x.id);
    const policy: MenuEntry[] = (["authorized", "conditional", "unauthorized"] as const).map((s) => ({
      label: s === "authorized" ? "Autorizar" : s === "conditional" ? "Con condiciones" : "No autorizar",
      icon: <StatusDot kind={authDot(s)} size="sm" />, hint: s === "authorized" ? "A" : s === "conditional" ? "C" : "N",
      checked: !many && p.status === s, onSelect: () => classify(selection, s),
    }));
    const category: MenuEntry = { label: "Cambiar categoría", submenu: Object.entries(CATEGORY_LABEL).map(([k, l]) => ({
      label: l, onSelect: () => patch(ids, { category: k, reason: "Categoría desde el menú de acciones" }, "Categoría actualizada"),
    })) };
    if (many) {
      return [
        ...(can.write ? [...policy, "separator" as const, category,
          { label: "Marcar como componentes", onSelect: () => patch(ids, { is_relevant: false, reason: "Marcado como componente" }, "Marcados como componentes") }] : []),
        "separator",
        { label: "Copiar nombres", onSelect: () => navigator.clipboard?.writeText(selection.map((x) => x.name).join("\n")) },
      ];
    }
    return [
      { label: "Abrir ficha", hint: "Intro", onSelect: () => nav(`/software/${p.id}`) },
      { label: p.devices !== undefined ? `Ver los ${p.devices} equipos que la tienen` : "Ver los equipos que la tienen",
        onSelect: () => nav(`/software/${p.id}?tab=instalaciones`) },
      ...(can.write ? [
        "separator" as const, ...policy,
        { label: "Excepción para departamento o equipo…", onSelect: () => nav(`/software/${p.id}?tab=politicas`) },
        ...(p.status === "unauthorized" ? [
          "separator" as const,
          { label: "Avisar a quien la tiene instalada…", onSelect: () => setNotifying(p.id) },
          { label: p.devices !== undefined ? `Desinstalar de los ${p.devices} equipos…` : "Desinstalar de los equipos…", danger: true,
            onSelect: () => setUninstalling(p.id) },
        ] : []),
        "separator" as const, category,
        { label: "Marcar como componente", onSelect: () => patch([p.id], { is_relevant: false, reason: "Marcado como componente" }, "Marcado como componente") },
        { label: "Fusionar con otro producto…", onSelect: () => setMerging({ product: p, target: "", reason: "" }) },
      ] : []),
      "separator",
      { label: "Copiar nombre", onSelect: () => navigator.clipboard?.writeText(p.name).then(() => toast("ok", "Nombre copiado")) },
      { label: "Exportar sus instalaciones", onSelect: () => api.download(`/software/${p.id}/installations/export`, { format: "xlsx" })
        .catch((e: Error) => toast("danger", e.message)) },
    ];
  };

  const remote: ReactNode = <>
    {notifying !== null && <NotifyDialog scope={{ product_id: notifying }} onClose={() => setNotifying(null)} />}
    {uninstalling !== null && <UninstallDialog productId={uninstalling} onClose={() => setUninstalling(null)} />}
  </>;

  const mergeDialog: ReactNode = merging && (
    <Modal open onClose={() => setMerging(null)} title={`Fusionar ${merging.product.name}`} footer={<>
      <Button onClick={() => setMerging(null)}>Cancelar</Button>
      <Button variant="primary" loading={mergeBusy} disabled={!Number(merging.target) || merging.reason.trim().length < 3}
        onClick={async () => {
          setMergeBusy(true);
          try {
            await api.send("POST", `/software/${Number(merging.target)}/merge`, { source_ids: [merging.product.id], reason: merging.reason });
            KEYS.forEach((k) => qc.invalidateQueries({ queryKey: k }));
            toast("ok", "Productos fusionados");
            setMerging(null);
          } catch (e) {
            toast("danger", (e as Error).message);
          } finally {
            setMergeBusy(false);
          }
        }}>Fusionar</Button>
    </>}>
      <div className="space-y-4">
        <p className="text-sm text-muted">Sus instalaciones y alias pasan al producto destino. El original se conserva para la trazabilidad.</p>
        <Field label="Id del producto destino" hint="Está en la dirección de su ficha: /software/<id>">
          {(id) => <input id={id} inputMode="numeric" className="field" autoFocus value={merging.target}
            onChange={(e) => setMerging({ ...merging, target: e.target.value.replace(/\D/g, "") })} />}
        </Field>
        <Field label="Motivo (queda en auditoría)">
          {(id) => <input id={id} className="field" value={merging.reason} onChange={(e) => setMerging({ ...merging, reason: e.target.value })} />}
        </Field>
      </div>
    </Modal>
  );

  return { entries, dialogs: <>{mergeDialog}{remote}</>, classify };
}
