import {
  InteractionRequiredAuthError,
  PublicClientApplication,
  type AccountInfo,
} from "@azure/msal-browser";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setTokenProvider } from "./api";
import type { Me } from "./types";

interface PublicConfig {
  auth_mode: "entra" | "dev";
  tenant_id: string;
  client_id: string;
  api_scope: string | null;
  version: string;
  environment: string;
}

interface AuthState {
  me: Me;
  config: PublicConfig;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth fuera de AuthProvider");
  return ctx;
}

export const useCan = () => useAuth().me.permissions;

async function setupMsal(cfg: PublicConfig): Promise<{ account: AccountInfo; msal: PublicClientApplication }> {
  const msal = new PublicClientApplication({
    auth: {
      clientId: cfg.client_id,
      authority: `https://login.microsoftonline.com/${cfg.tenant_id}`,
      redirectUri: window.location.origin,
    },
    cache: { cacheLocation: "sessionStorage" },
  });
  await msal.initialize();
  const redirect = await msal.handleRedirectPromise();
  const account = redirect?.account ?? msal.getAllAccounts()[0];
  if (!account) {
    await msal.loginRedirect({ scopes: [cfg.api_scope!] });
    return new Promise(() => {}); // la página se redirige
  }
  msal.setActiveAccount(account);
  return { account, msal };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const config = await api.get<PublicConfig>("/config/public");
      let signOut = () => window.location.reload();
      if (config.auth_mode === "entra") {
        const { account, msal } = await setupMsal(config);
        setTokenProvider(async () => {
          try {
            const r = await msal.acquireTokenSilent({ scopes: [config.api_scope!], account });
            return r.accessToken;
          } catch (e) {
            if (e instanceof InteractionRequiredAuthError) {
              await msal.acquireTokenRedirect({ scopes: [config.api_scope!], account });
            }
            throw e;
          }
        });
        signOut = () => void msal.logoutRedirect({ account });
      }
      const me = await api.get<Me>("/me");
      if (!cancelled) setState({ me, config, signOut });
    })().catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <div className="grid min-h-screen place-items-center p-6">
        <div className="card max-w-md p-6 text-center">
          <h1 className="text-base font-semibold">No se pudo iniciar sesión</h1>
          <p className="mt-2 text-muted">{error}</p>
          <button className="mt-4 text-accent underline" onClick={() => window.location.reload()}>
            Reintentar
          </button>
        </div>
      </div>
    );
  }
  if (!state) {
    return (
      <div className="grid min-h-screen place-items-center text-muted" role="status">
        Cargando Inventario Asserta…
      </div>
    );
  }
  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

/** Para pruebas de componentes. */
export function TestAuthProvider({ me, children }: { me: Me; children: ReactNode }) {
  const config: PublicConfig = { auth_mode: "dev", tenant_id: "", client_id: "", api_scope: null, version: "test",
    environment: "test" };
  return <AuthContext.Provider value={{ me, config, signOut: () => {} }}>{children}</AuthContext.Provider>;
}
