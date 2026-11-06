"""Despierta al worker cuando se encola trabajo (despliegue en la nube).

En la nube el worker no es un proceso permanente: lo ejecuta GitHub Actions cada hora
(.github/workflows/worker.yml, disparado por pg_cron de Supabase). Para que «Sincronizar ahora»
o una subida de fichero no esperen a la siguiente hora, la API lanza el workflow en el momento
con la API workflow_dispatch de GitHub.

Es «mejor esfuerzo»: si falla, la ejecución queda en cola y la procesa la siguiente pasada horaria.
Sin INV_WORKER_DISPATCH_TOKEN (instalación local con worker continuo) no hace nada.
"""
from __future__ import annotations

import logging
import threading

import httpx

from app.core.config import get_settings

log = logging.getLogger("inventario.dispatch")


def _post(url: str, token: str, ref: str) -> None:
    try:
        resp = httpx.post(url, json={"ref": ref}, timeout=8.0, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "asserta-inventario",
        })
        if resp.status_code != 204:
            log.warning("No se pudo lanzar el worker (HTTP %s): %s", resp.status_code, resp.text[:200])
    except httpx.HTTPError as exc:
        log.warning("No se pudo lanzar el worker: %s", exc)


def wake_worker(*, wait: bool = False) -> bool:
    """Lanza el workflow del worker. Devuelve False si no está configurado.

    En una función de Vercel la respuesta puede enviarse antes de que termine un hilo suelto,
    así que allí se espera (wait=True por defecto en serverless): son ~200 ms.
    """
    s = get_settings()
    if not (s.worker_dispatch_token and s.worker_dispatch_repo):
        return False
    url = (f"https://api.github.com/repos/{s.worker_dispatch_repo}/actions/workflows/"
           f"{s.worker_dispatch_workflow}/dispatches")
    if wait or s.serverless:
        _post(url, s.worker_dispatch_token, s.worker_dispatch_ref)
    else:
        threading.Thread(target=_post, args=(url, s.worker_dispatch_token, s.worker_dispatch_ref), daemon=True).start()
    return True
