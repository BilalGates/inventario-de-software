import { useMutation, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useToast } from "@/components/ui";

/** Estado de listas en la URL (filtros, orden, página) para poder compartir y volver atrás. */
export function useUrlState<K extends string>(keys: readonly K[]) {
  const [params, setParams] = useSearchParams();
  const values = Object.fromEntries(keys.map((k) => [k, params.get(k)])) as Record<K, string | null>;
  const set = (patch: Partial<Record<K | "page", string | number | null>>, resetPage = true) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === undefined || v === "") next.delete(k);
      else next.set(k, String(v));
    }
    if (resetPage && !("page" in patch)) next.delete("page");
    setParams(next, { replace: true });
  };
  const page = Number(params.get("page") ?? 1) || 1;
  return { values, set, page };
}

/** Mutación con aviso de éxito/error e invalidación de consultas. */
export function useAction<TVars, TRes = unknown>(
  fn: (v: TVars) => Promise<TRes>,
  opts: { success?: string | ((r: TRes) => string); invalidate?: QueryKey[]; onSuccess?: (r: TRes) => void } = {},
) {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: fn,
    onSuccess: (r) => {
      opts.invalidate?.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      if (opts.success) toast("ok", typeof opts.success === "function" ? opts.success(r) : opts.success);
      opts.onSuccess?.(r);
    },
    onError: (e: Error) => toast("danger", e.message),
  });
}
