# Depurar: el cambio mínimo

Regla de oro: **el diff de un arreglo debe poder leerse en diez segundos.** Si no se entiende qué se ha hecho, está mal hecho aunque funcione.

## 1. Diagnosticar sin tocar

- **Reproduce** con un comando o pasos exactos. Copia el error literal. Lee la traza de abajo arriba hasta el primer fichero del proyecto.
- **Lee el flujo entero** de la zona afectada antes de proponer nada: quién llama, qué datos llegan.
- Busca con grep **todos los que llaman** a la función sospechosa. Un guard en la función compartida es un diff más pequeño que un guard en cada llamador.
- Pregunta qué cambió: `git log -p -- <fichero>`; `git bisect` si hay un commit bueno conocido.
- **Hipótesis una a una con evidencia**: tests, la consulta, el valor real en el depurador o la salida de un comando. No leer y suponer.

**Ninguna edición hasta tener la causa raíz con evidencia.** Declárala: `Causa: fichero:línea — por qué.`

## 2. Logs: solo si no hay otra forma

Antes de un `console.log` prueba, por este orden: leer el código, un test que lo reproduzca, el depurador, una consulta directa o la salida existente.
Si aun así hace falta:
- Como mucho 1–3 líneas, todas marcadas: `console.log("…") // filigrana:debug`
- Se borran antes de entregar. Comprueba con `grep -rn "filigrana:debug" .` → debe dar 0.

## 3. Presupuesto de diff

Antes de editar, anuncia en una línea: **"Tocaré N líneas en M ficheros: <qué>."**
- Lo normal es 1–10 líneas en 1–2 ficheros.
- Si te pasas: **para** y explica por qué el arreglo mínimo no basta antes de seguir.
- Tras editar: `git diff --stat` debe coincidir con lo anunciado.

## 4. Prohibido mientras se arregla

- Refactorizar, renombrar, reordenar imports, reformatear o "limpiar de paso".
- Ficheros nuevos, helpers nuevos, dependencias nuevas.
- Código defensivo en otros sitios "por si acaso".
- Silenciar: `try/catch` vacío, `?? []` que esconde el fallo, `@ts-ignore`, `eslint-disable`, `any`.
- Arreglar tres cosas a la vez. Lo que veas fuera de alcance va a la lista de **"Visto, no tocado"**.

## 5. Blindar (lo justo)

- Si hay suite: un test que reproduce el fallo, **verlo fallar**, arreglar, verlo pasar. Ejecuta la suite del módulo.
- Si no hay suite: la comprobación ejecutable más pequeña (el comando de reproducción ahora pasa).
- Busca el mismo patrón en otros sitios: avísalo, no lo arregles sin permiso.

## 6. Si te atascas

Dos hipótesis fallidas → **para**. Resume lo descartado con su evidencia y pide segunda opinión de otro modelo:
```bash
node DIR/scripts/delegar.mjs --motor codex --nivel fuerte "Bug: <síntoma>. Reproducción: <cmd>. Descartado: <…>. Encuentra la causa raíz; no propongas refactors."
```
Contrasta su hipótesis con evidencia antes de aceptarla.

## 7. Entrega

```
Síntoma:   …
Causa:     fichero:línea — por qué
Arreglo:   N líneas en M ficheros — qué y por qué es lo mínimo
Prueba:    comando/test → falla antes, pasa después
Visto, no tocado: … (opcional)
```
Nada más. Sin explicar el arreglo línea a línea si el diff se entiende solo.
