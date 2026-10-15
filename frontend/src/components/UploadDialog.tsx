import { useQueryClient } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAction } from "@/lib/hooks";
import type { Run } from "@/lib/types";
import { Button, Field, Modal, Notice } from "./ui";

/** Subida de una exportación de Panda (un equipo) o de un CSV de Intune (contingencia). */
export function UploadDialog({ source, deviceId, deviceName, onClose }: {
  source: "panda" | "intune"; deviceId?: number; deviceName?: string; onClose: () => void;
}) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [complete, setComplete] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const send = useAction(() => {
    const fd = new FormData();
    fd.set("source", source);
    fd.set("file", file!);
    if (deviceId) fd.set("device_id", String(deviceId));
    fd.set("declared_complete", String(complete));
    return api.upload<Run>("/runs/upload", fd);
  }, {
    success: "Fichero recibido: se procesará en segundos",
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      onClose();
      nav("/sincronizacion");
    },
  });

  return (
    <Modal open onClose={onClose} title={source === "panda" ? "Importar exportación de Panda" : "Importar CSV de Intune"}
      footer={<>
        <Button onClick={onClose}>Cancelar</Button>
        <Button variant="primary" disabled={!file} loading={send.isPending} onClick={() => send.mutate(undefined)}>Importar</Button>
      </>}>
      <div className="space-y-4">
        {source === "panda" ? (
          <p className="text-muted">
            Exportación del software de un equipo en Panda Adaptive Defense (texto separado por tabuladores o
            copiado desde la consola).{" "}
            {deviceName ? <>Se asociará a <strong className="text-fg">{deviceName}</strong>.</>
              : <>El equipo se identifica por el nombre del fichero: <span className="kbd">HOSTNAME.txt</span>.</>}
          </p>
        ) : (
          <p className="text-muted">CSV de dispositivos o de aplicaciones exportado del portal de Intune o del script de inventario. El tipo se detecta por las columnas.</p>
        )}
        <Field label="Fichero">
          {(id) => (
            <div>
              <input id={id} ref={input} type="file" accept={source === "panda" ? ".txt,.tsv,.csv" : ".csv"} className="sr-only"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              <button type="button" onClick={() => input.current?.click()}
                className="flex w-full flex-col items-center gap-1 rounded-md border border-dashed border-border px-4 py-6 text-muted hover:border-accent hover:text-fg">
                <FileUp className="size-5" aria-hidden />
                {file ? <span className="text-fg">{file.name} · {(file.size / 1024).toFixed(0)} KB</span> : "Seleccionar fichero"}
              </button>
            </div>
          )}
        </Field>
        {source === "intune" && (
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={complete} onChange={(e) => setComplete(e.target.checked)} className="mt-0.5 accent-[rgb(var(--accent))]" />
            <span>La exportación de aplicaciones es completa para los equipos que contiene.
              <span className="block text-xs text-muted">Solo entonces se registrarán como desinstaladas las aplicaciones que falten.</span></span>
          </label>
        )}
        <Notice tone="info">Reimportar el mismo fichero no duplica datos.</Notice>
      </div>
    </Modal>
  );
}
