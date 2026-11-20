# Informe — Ocultar «Listas Precios» (general, #35) en SAC

Autor: Eco Coder 1 · 20-nov-2026 · rama `coder-1/ocultar-listas-sac` · código `335f561` (base develop `31ba117`)
Nivel: **lógica**. QA 1 lo subió porque `Sidebar.tsx` y `ConfigLayout.tsx` los pintan las 7 orgs.

## 1. Qué cambió

- **Sidebar:** los hijos de una sección ahora respetan `hideWhenOrgFlag` (#77), igual que las entradas de primer nivel. «Listas Precios» lo declara con `kg_ledger_enabled`.
- **ConfigLayout:** la pestaña «Precios» lo declara igual, y el filtro de pestañas lo respeta.
- **Degradación #77:** mientras los settings cargan o fallan, la entrada se ve. Medido con settings en 500 (`degradacion.log`, PASS).
- **La ruta `/config/price-lists` sigue viva:** solo sale del menú. El barrido de rutas entrantes está en `barrido.log`.

## 2. Matriz del plantado (commiteada ANTES de plantar)

**Instrumento:** `capturas_config.mjs`, alto 1600, 6 capturas por corrida: Costa y SAC × `config-1440`, `pestanas-390` y `sidebar-390`.

**Medición:**
- Cada captura se compara por sha256 contra la de `335f561` (`despues_*`).
- Antes de plantar se corre un **C0 sin defecto**, que tiene que dar las 6 idénticas. Si no, el instrumento no es determinista y las filas no miden nada.
- Cada fila restaura el archivo desde la copia por ruta y verifica su sha256 (Sidebar `8119f67b…`, ConfigLayout `a79736ec…`).
- El cierre va con `git status` vacío y `git diff --stat 335f561` vacío.

| P | Defecto plantado | Debe cambiar | NO debe cambiar | Puede cambiar de más |
|---|---|---|---|---|
| P1 | quitar `&& checkHide(child.hideWhenOrgFlag)` del filtro de hijos (Sidebar) | sac_sidebar-390, sac_config-1440 («Listas Precios» vuelve) | costa ×3, sac_pestanas-390 | — |
| P2 | quitar la condición `hideWhenOrgFlag` del filtro de pestañas (ConfigLayout) | sac_pestanas-390, sac_config-1440 («Precios» vuelve) | costa ×3 | sac_sidebar-390 (el drawer puede dejar ver la barra de pestañas) |
| P3 | invertir `checkHide` a `!flag \|\| flagEnabled(flag)` (Sidebar) | costa_sidebar-390, costa_config-1440 (Costa pierde Compras, Materiales y Listas Precios) | costa_pestanas-390, sac_pestanas-390 | sac_sidebar-390, sac_config-1440 (SAC recupera esas tres) |

- La dirección peligrosa es que una captura de «Debe cambiar» salga idéntica.
- P3 es la fila que prueba que la comparación de Costa discrimina: con ese defecto, Costa tiene que salir distinta.

## 3. Gates

- **Lint, tsc, build y guardas:** corridos en la entrega de `335f561`. Logs en `~/sac-evidencia/2026-11-20/coder-1-ocultar-listas-sac/`.
- **Dirigidas:** el comando `grep -rln "Sidebar\|ConfigLayout" backend/tests` y su resultado van en `dirigidas.log`. Si sale vacío, no aplican más allá de las tres guardas.
- **Golden:** no aplica. El cambio no toca backend, y el golden captura respuestas HTTP.
- **Plantado:** resultados en §4 (se llena después de plantar, sin tocar §2).
