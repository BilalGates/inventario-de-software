/** Cliente HTTP de la API. El token (Entra ID) lo aporta el proveedor de autenticación. */

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

let tokenProvider: (() => Promise<string | null>) | null = null;

export function setTokenProvider(fn: (() => Promise<string | null>) | null) {
  tokenProvider = fn;
}

async function headers(extra?: HeadersInit): Promise<Headers> {
  const h = new Headers(extra);
  const token = tokenProvider ? await tokenProvider() : null;
  if (token) h.set("Authorization", `Bearer ${token}`);
  return h;
}

async function handle<T>(res: Response): Promise<T> {
  if (res.ok) {
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }
  let message = `Error ${res.status}`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") message = body.detail;
  } catch {
    /* respuesta sin JSON */
  }
  if (res.status === 401) message = "Su sesión ha caducado. Vuelva a iniciar sesión.";
  if (res.status === 403 && message.startsWith("Error")) message = "No tiene permisos para esta operación.";
  throw new ApiError(res.status, message);
}

type Params = Record<string, string | number | boolean | null | undefined>;

export function qs(params?: Params): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const api = {
  async get<T>(path: string, params?: Params): Promise<T> {
    return handle<T>(await fetch(`/api${path}${qs(params)}`, { headers: await headers() }));
  },
  async send<T>(method: "POST" | "PATCH" | "PUT" | "DELETE", path: string, body?: unknown): Promise<T> {
    const res = await fetch(`/api${path}`, {
      method,
      headers: await headers(body !== undefined ? { "Content-Type": "application/json" } : undefined),
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    return handle<T>(res);
  },
  async upload<T>(path: string, form: FormData): Promise<T> {
    return handle<T>(await fetch(`/api${path}`, { method: "POST", headers: await headers(), body: form }));
  },
  /** Descarga autenticada (exportaciones e informes). */
  async download(path: string, params?: Params): Promise<void> {
    const res = await fetch(`/api${path}${qs(params)}`, { headers: await headers() });
    if (!res.ok) await handle(res);
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") ?? "";
    const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? "export";
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  },
};
