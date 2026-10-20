"""Graph simulado para pruebas de conector (sin red)."""
from __future__ import annotations

import json
from collections.abc import Callable

import httpx

from app.connectors.graph import GraphClient

BASE = "https://graph.microsoft.com"


def device(i: int, **over) -> dict:
    d = {
        "id": f"intune-{i}", "deviceName": f"PC-{i:03d}", "azureADDeviceId": f"entra-{i}",
        "serialNumber": f"SN{i:06d}", "manufacturer": "Dell Inc.", "model": "Latitude 5440",
        "operatingSystem": "Windows", "osVersion": "10.0.22631.4317", "userPrincipalName": f"user{i}@asserta.test",
        "userDisplayName": f"Usuario {i}", "enrolledDateTime": "2025-01-10T09:00:00Z",
        "lastSyncDateTime": "2026-10-14T08:00:00Z", "complianceState": "compliant", "managementState": "managed",
        "isEncrypted": True, "totalStorageSpaceInBytes": 512_000_000_000, "freeStorageSpaceInBytes": 200_000_000_000,
        "physicalMemoryInBytes": 0, "wiFiMacAddress": "001122334455", "ethernetMacAddress": "",
        "managedDeviceOwnerType": "company",
    }
    d.update(over)
    return d


class FakeGraph:
    """Simula managedDevices, detectedApps y sus relaciones, con paginación y fallos inyectables."""

    def __init__(self, devices: list[dict], apps: dict[str, list[str]], page_size: int = 2):
        # apps: "Nombre|Editor|Versión" -> [intune ids]
        self.devices = devices
        self.apps = [
            {"id": f"app-{n}", "displayName": k.split("|")[0], "publisher": k.split("|")[1],
             "version": k.split("|")[2], "platform": "windows", "_devices": v}
            for n, (k, v) in enumerate(apps.items())
        ]
        self.page_size = page_size
        self.fail: Callable[[httpx.Request], httpx.Response | None] = lambda req: None
        self.calls: list[str] = []

    def _page(self, items: list[dict], request: httpx.Request) -> httpx.Response:
        skip = int(request.url.params.get("$skiptoken", "0"))
        chunk = items[skip: skip + self.page_size]
        body = {"value": [{k: v for k, v in it.items() if not k.startswith("_")} for it in chunk]}
        if skip + self.page_size < len(items):
            url = request.url.copy_merge_params({"$skiptoken": str(skip + self.page_size)})
            body["@odata.nextLink"] = str(url)
        return httpx.Response(200, json=body)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(f"{request.method} {request.url.path}")
        if request.url.host == "login.microsoftonline.com":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if (injected := self.fail(request)) is not None:
            return injected
        path = request.url.path.removeprefix("/v1.0").removeprefix("/beta")
        if path == "/deviceManagement/managedDevices":
            return self._page(self.devices, request)
        if path.startswith("/deviceManagement/managedDevices/") and path.count("/") == 3:
            dev_id = path.rsplit("/", 1)[1]
            if request.url.params.get("$expand") == "detectedApps":
                # Como el beta real: sin editor y con paquetes del sistema que no están en el catálogo.
                # Además, con otro id que el catálogo (como hace Graph con la mayoría de apps).
                apps = [{**{k: v for k, v in a.items() if not k.startswith("_")}, "id": f"beta-{a['id']}",
                         "publisher": None} for a in self.apps if dev_id in a["_devices"]]
                if apps:
                    apps.append({"id": "pkg-sistema", "displayName": "Microsoft.WindowsStore", "publisher": None})
                return httpx.Response(200, json={"id": dev_id, "detectedApps": apps})
            return httpx.Response(200, json={"id": dev_id, "physicalMemoryInBytes": 16 * 1024**3})
        if path == "/deviceManagement/detectedApps":
            return self._page(self.apps, request)
        if path.startswith("/deviceManagement/detectedApps/") and path.endswith("/managedDevices"):
            app_id = path.split("/")[3]
            app = next(a for a in self.apps if a["id"] == app_id)
            return self._page([{"id": d, "deviceName": d} for d in app["_devices"]], request)
        if path.startswith("/deviceManagement/managedDevices/") and path.endswith("/detectedApps"):
            dev_id = path.split("/")[3]
            return self._page([a for a in self.apps if dev_id in a["_devices"]], request)
        return httpx.Response(404, json={"error": {"code": "NotFound"}})

    def client(self) -> GraphClient:
        http = httpx.Client(transport=httpx.MockTransport(self.handler))
        return GraphClient("tenant", "client", "secret", http=http, sleep=lambda s: None, max_retries=3)


def dumps(o) -> str:
    return json.dumps(o)
