---
name: seguridad-web
description: Checklist de seguridad para aplicaciones web — autenticación, sesiones, autorización en servidor, acciones destructivas, secretos, inyección, almacenamiento de ficheros y superficie de API. Cárgala al construir o revisar cualquier cosa que toque auth, permisos, datos sensibles o endpoints.
---

# seguridad-web

Supón un atacante **con cuenta válida** que intenta hacer más de lo que le toca.

## Autenticación y sesión

- Cookies `httpOnly`, `Secure`, `SameSite`; caducidad y renovación; revocación efectiva.
- Reset e invitación: tokens de un solo uso, con caducidad, no adivinables; no revelan si un correo existe.
- OAuth: `state` validado, redirect URIs cerradas.
- Límite de intentos en login y endpoints sensibles.

## Autorización

- **Todo** endpoint, acción de servidor o handler comprueba permiso en servidor. Un guard solo en la interfaz no es un guard.
- Todo id que llega del cliente (URL, payload, cuerpo) es hostil: comprueba que pertenece al usuario/tenant de la sesión.
- Escalada: ¿puede alguien cambiar su propio rol, su organización o su supervisor?
- Roles de solo lectura: ninguna escritura alcanzable.

## Acciones destructivas

- Confirmación explícita (modal propio, nunca `window.confirm`), alcance real de los borrados en cascada, quién puede invocarlos, registro de auditoría.

## Secretos

- Cero secretos en el repo, en logs o en errores. Nada sensible expuesto al cliente (prefijos públicos de framework).
- Tokens de terceros cifrados en reposo. Comparación de secretos en tiempo constante.

## Inyección y entrada

- SQL siempre parametrizado; nunca interpolar entrada en SQL, shell, HTML ni rutas.
- Validar tipo, tamaño y forma de toda entrada en servidor. Sanitizar HTML de terceros.

## Ficheros

- URLs firmadas con TTL corto, permiso validado antes de firmar, clave prefijada por tenant/propietario. Ningún bucket público.
- Validar tipo real y tamaño de las subidas.

## API

- Autenticado por defecto; excepciones justificadas y listadas.
- Errores que no revelan estructura interna ni existencia de recursos ajenos.
- Cabeceras de seguridad (CSP, HSTS, frame-ancestors).

## Severidad

CRÍTICO (explotable, datos o cuentas ajenas) · ALTO (explotable con condiciones) · MEDIO (defensa en profundidad ausente) · BAJO (higiene). Sin vector concreto, no es CRÍTICO.
