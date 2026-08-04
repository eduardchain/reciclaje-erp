# Plan — Paquete UX pre-commit: config unificada de materiales SAC + UI de retenciones

**Disparador:** walkthrough manual de Daniel (2026-07-16) sobre el conjunto {E2 − subtype + material_kg_profiles} — QA ya dio GO al conjunto base; Daniel decidió incorporar este paquete ANTES del commit atómico (re-QA del conjunto ampliado). Comentarios origen: C1/C3/C4/C5 (config de materiales) + GAP-1 (retenciones sin UI). Registro completo en scratchpad `walkthrough-comentarios.md`.

**Naturaleza:** 100% frontend. Cero backend, cero migraciones, cero endpoints nuevos. El re-QA es tsc+build+lectura+pruebas manuales; la suite backend (1258) se re-corre como regresión general y debe quedar idéntica.

**Decisiones de Daniel (2026-07-16):**
- El formulario unificado TAMBIÉN crea el material (código/nombre/unidad/categoría + clasificación + factor, un submit).
- El concepto `willard_world` se presenta como **"Clasificación"** (genérico, sin marca de cliente).

---

## 1. Alcance

### ENTRA
- **A. Página unificada de materiales SAC** (C1+C3+C5): reemplaza el contenido de Config→Formulas por una tabla **material-céntrica** + formulario único crear/editar.
- **A4. C4 mitigado**: "Compra regular" es la clasificación default; check ortogonal visible solo en el caso Willard.
- **A5. C2 versión SAC**: unidad como **dropdown** (`kg`/`unidad`) en el form SAC-only. El `MaterialFormDialog` compartido (prod) NO se toca.
- **B. UI de retenciones** (GAP-1): sección en `PurchaseLiquidatePage` + visualización en `PurchaseDetailPage`, gated por flag.

### NO ENTRA (bloqueado por respuestas pendientes — NO implementar "por si acaso")
- C6 sede determinista por mundo (Q-05 Johana/Hugo).
- C7 recepción-compra vs módulo compras (Q-06).
- C4 exclusión total del modelo — enum en vez de bool+world (Q-04).
- C2 en el maestro compartido (backlog transversal con su propio QA).

---

## 2. Diseño A — Página "Materiales (kg)" (Config, misma ruta `/config/formulas`)

### 2.1 Tabla material-céntrica
Fuente: `useMaterials` + `useKgProfiles` + `useCurrentFormulas` — join client-side por `material_id` (cero backend nuevo). Lista **TODOS** los materiales activos de la org:

| Columna | Contenido |
|---|---|
| Material | `CODE - Nombre (unidad)` |
| Clasificación | Badge: **Sin clasificar** (gris, sin perfil) / **Compra regular** (emerald) / **Postconsumo (baterías)** (índigo) / **Drosses** (teal). Si Willard + compra_regular=true, badge secundario "Compra". |
| Factor vigente | `8 kg/unidad` / `53% plomo` / `—` (sin fórmula) |
| Desde / Por | de la fórmula vigente (— si no hay) |
| Acciones | Editar (lápiz, abre el form unificado) · Historial (fórmulas) |

- Búsqueda por código/nombre (client-side) + filtro por clasificación (select).
- Resuelve C5: un material clasificado sin factor **aparece** con su badge; ya no "desaparece".
- Header: botón único **"Nuevo Material"** (reemplaza "Clasificar Material" + "Nueva Formula"). Los dialogs viejos se eliminan.

### 2.2 Formulario unificado (crear + editar, mismo dialog)
Campos en orden:
1. **Código*** / **Nombre*** — código inmutable en editar (convención).
2. **Unidad***: dropdown `kg` | `unidad` (C2-SAC). En **editar**: solo-lectura si el material tiene fórmula vigente (cambiarla rompería la coherencia unidad↔tipo del histórico); hint "La unidad no se cambia con fórmula vigente".
3. **Categoría***: select de categorías de material.
4. **Clasificación***: select — **Compra regular** (default) | **Postconsumo (baterías)** | **Drosses**.
   - `Compra regular` ⇒ `compra_regular=true, willard_world=none`.
   - Willard ⇒ `willard_world=X, compra_regular=false` + check condicional **"También entra por compra regular"** (visible solo en Willard, default desmarcado) — preserva la ortogonalidad del modelo sin ensuciar el caso común (C4 mitigado; la exclusión definitiva espera Q-04).
5. **Factor** (visible solo si clasificación = Willard; la unidad deriva el tipo, texto informativo "Unidad 'X' → tipo"):
   - `unidad` → "Kg de plomo por unidad*" + referencia opcional.
   - `kg` → "% de plomo*".
   - En **editar** con factor existente: mostrar vigente; si el usuario lo cambia → POST nueva fórmula (append-only, historial intacto). Sin cambio → no se postea nada.
6. Notas de fórmula (opcional, solo si hay factor).

**Submit encadenado (crear):** `POST /materials` → `PUT /material-kg-profiles/{id}` → `POST /material-conversion-formulas` (solo Willard). **Fallo parcial:** sin rollback distribuido (mismo riesgo que el flujo manual actual de 3 forms) — toast específico de qué paso falló; el material queda visible como "Sin clasificar" → reintentar desde Editar. Documentado como comportamiento aceptado.

**Submit (editar):** `PATCH /materials/{id}` (F1 QA: el endpoint es PATCH, no PUT — usar siempre `materialsService.update`, nunca llamada cruda) solo si cambió nombre/categoría/unidad; `PUT` perfil solo si cambió clasificación; `POST` fórmula solo si cambió factor. Diffs mínimos.

### 2.3 Renombres C3 (SAC-only, cero prod)
- Sidebar Config: "Formulas" → **"Materiales (kg)"**.
- Todo "Mundo Willard" → **"Clasificación"**; labels de valores según 2.1.
- `WILLARD_WORLD_LABELS` en `types/sac-config.ts` es la única fuente de labels (ya lo es).
- El texto de ayuda del ruteo se conserva reescrito: "Los kg de una recepción Willard van a la cuenta según la clasificación del material."
- Error backend "no es de mundo Willard" (inbound_order.py:200-204): **queda igual** — es backend y el paquete es frontend-only; anotado para el ciclo B si molesta.

## 3. Diseño B — UI de retenciones en liquidación (GAP-1)

### 3.1 `PurchaseLiquidatePage` — sección "Retenciones" 
- **Gating:** visible solo con `kg_ledger_enabled` (via `useOrgSettings`). Flag OFF ⇒ payload sin `retentions` ⇒ **byte-idéntico a hoy** (guardrail prod).
- Lista dinámica de filas (patrón FormLineGrid/comisiones): **Tipo** (select ReteFuente/ReteIVA/ICA) · **Municipio** (input, visible y obligatorio solo en ICA) · **Monto** (MoneyInput). `rate`/`base_amount` del schema se omiten en v1 (opcionales informativos; el backend acepta null).
- **Preview del neto:** "Total: $X · Retenciones: −$Y · **Neto al proveedor: $Z**". Validación client-side Σret < total (el backend 422 es la red).
- **Pago inmediato:** si está activo, el monto mostrado/pagado es el **NETO** (el backend ya paga neto — la UI debe decirlo explícito para no descuadrar al operador).
- Payload: `retentions: [{retention_type, municipality?, amount}]` — ausente si no hay filas.

### 3.2 `PurchaseDetailPage` — "Retenciones aplicadas"
Sección visible si `purchase.retentions.length > 0`: tipo, municipio (ICA), monto, y suma con nota "Proveedor acreditado por el neto". (El response ya trae `retentions[]` — decisión #75.)

### 3.3 Types
`types/purchase.ts`: `PurchaseRetentionCreate`, `PurchaseRetentionResponse`, `retentions?` en el payload de liquidate y en `PurchaseResponse`.

---

## 4. Guardrails (no-tocar)
1. **`MaterialFormDialog` compartido**: intacto (D4/D5 del ciclo anterior siguen vigentes).
2. **Backend**: cero cambios — si durante el código aparece necesidad de backend, PARAR y re-planear.
3. **Flag OFF byte-idéntico**: liquidación sin flag no manda `retentions`; página Materiales (kg) ya estaba gated.
4. **Fallback sin-perfil de recepción-compra** (`?? true`): sin cambio.
5. **Append-only de fórmulas**: editar factor = POST nueva, nunca mutar.

## 5. Riesgos / edges
- **Fallo parcial del encadenado** (2.2) — aceptado y visible ("Sin clasificar" + toast). 
- **Unidad editable**: bloqueada con fórmula vigente (el edge real: cambiar kg→unidad dejaría una fórmula % sobre material por unidad).
- **Org con muchos materiales**: búsqueda + filtro client-side (magnitud SAC: decenas — OK).
- **Retenciones + flag off en el MISMO render** (org cambia de org selector): la sección desaparece y el estado local de filas se descarta — aceptable.

## 6. Verificación
1. `npx tsc --noEmit` + `npm run build` limpios.
2. Suite backend re-run completa == 1258 (regresión: el paquete no la toca).
3. Grep guardrail: `git diff --stat backend/` == vacío para este paquete.
4. **Walkthrough guiado (Daniel):**
   - Alta de material Willard completo en UN formulario (crear+clasificar+factor) — C1 resuelto.
   - Material compra regular: default correcto sin tocar checks — C4 resuelto.
   - Tabla muestra los 3 + "Sin clasificar" — C5 resuelto; cero "Mundo Willard" visible — C3.
   - Editar: cambiar factor (append, historial lo muestra), cambiar clasificación.
   - Liquidar la compra derivada con retefuente $X: preview neto, balance pasivo `[Retenciones] ReteFuente`, estado de cuenta del proveedor con evento sintético, pago inmediato por el neto.
   - Regresión visual: liquidación en org SIN flag (Costa dev) — sin sección retenciones, flujo intacto.
   - **(QA-a) Fallo parcial del encadenado**: forzar fallo del paso 2/3 (ej. crear material OK y perfil falla) → verificar "Sin clasificar" + toast del paso correcto + Editar recupera. Confirmarlo, no asumirlo.
   - **(QA-b) Editar cambiando SOLO el factor**: postea fórmula nueva (append) y el historial la muestra — guardrail §4.5 verificado en vivo.

**Forward-notes de QA (rastreadas, NO implementar aquí):**
- **F2 (E5 roles finos)**: el submit unificado encadena `materials.create` + `materials.edit` + `formulas.manage` — gatear el botón "Nuevo Material" en `materials.create` cuando lleguen los roles SAC granulares; hoy todos los testers son admin.
- **F3 (hardening backend)**: `PATCH /materials` acepta cambiar `default_unit` sin validar fórmulas existentes — el guard es solo frontend. Candidato a guard de servidor en un ciclo backend.

## 7. Archivos
- **Reescrito:** `pages/config/FormulasPage.tsx` (→ página Materiales (kg); mantiene ruta y nombre de archivo o se renombra — decisión cosmética al codificar).
- **Nuevo:** `components/.../MaterialUnifiedFormDialog.tsx` (o local a la página).
- **Modificados:** `PurchaseLiquidatePage.tsx`, `PurchaseDetailPage.tsx`, `types/purchase.ts`, `types/sac-config.ts` (labels), `Sidebar.tsx` (label), `constants.ts` (si hay labels ahí).
- **Backend:** NINGUNO *(superseded por el ADDENDUM §8: 2 endpoints chicos)*.

## 8. ADDENDUM (2026-07-17, aprobado por Daniel — VUELVE A QA por romper el gate "cero backend")

**Disparador:** preguntas de arquitectura de Daniel en el walkthrough ("¿dónde veo las cuentas de retención, sus estados de cuenta, cuánto se debe, dónde creo una?"). Decisiones de producto: **(a)** hogar = grupo "Retenciones" en Tesorería→Pasivos (opción A); **(b)** control de municipios ICA (selector, no texto libre) **dentro de este paquete** — Daniel juzga inaceptable el riesgo de typo-duplicado ("Baranquilla" ≠ "Barranquilla" crearía 2 entidades; el matching H4 solo cubre tildes/casing).

### 8.1 Principio arquitectónico
`is_system_entity` protege de **edición/borrado**, no de **visibilidad**. `[Prepago]` = artefacto interno → oculto (sin cambio). `[Retenciones]` = **acreedor real** (DIAN/municipio) → primera clase en el contexto de Pasivos.

### 8.2 Backend (rompe el gate — por eso este addendum va a QA)
**2 endpoints chicos en el router de third_parties, flag-gated (`require_org_flag("kg_ledger_enabled")`), CERO migraciones, CERO cambios al flujo de liquidación:**
1. `GET /third-parties/retention-entities` → lista estructurada `[{id, retention_type, municipality|null, name, current_balance, is_active}]`. Implementación: query de ThirdParty `is_system_entity=True AND name LIKE '[Retenciones]%'` de la org + **parseo server-side del formato canónico propio** (los prefijos son constantes de `services/purchase.py` — el server es dueño del formato; se extraen a módulo compartido para no duplicar). Alimenta el grupo en Pasivos Y el selector de municipio al liquidar. Permiso: `treasury.view_liabilities` (o el que hoy proteja LiabilitiesPage — verificar al codificar y usar el mismo).
2. `POST /third-parties/retention-entities` body `{retention_type: "ica", municipality: str}` → **reusa el get-or-create idempotente existente** (`_get_or_create_retention_entity` de purchase service, extraído/parametrizado a helper compartido; matching H4 intacto). Solo `ica` es creable manualmente (ReteFuente/ReteIVA son singleton auto). Permiso: el de crear pasivos en LiabilitiesPage (mismo — verificar al codificar).

**Sin cambios en `liquidate`**: el auto-create al liquidar QUEDA (compat API + tests D9 intactos); la restricción a lista es de UI. Declarado: la API cruda sigue permisiva.

### 8.3 Frontend
1. **LiabilitiesPage — grupo "Retenciones"** (visible solo si `GET` retorna >0; orgs prod: idéntica): tabla/cards con entidad, municipio, saldo (cuánto se debe), badge "Sistema" (no editable/desactivable desde aquí), acciones **[Estado de cuenta]** (link al statement estándar) y **[Pagar]** (navega a MovementCreate `liability_payment` con tercero pre-llenado — mecanismo `initialThirdPartyId` existente). Botón **"Agregar municipio ICA"** → dialog con input municipio → POST (responde "¿dónde creo una nueva?").
2. **PurchaseLiquidatePage — municipio ICA pasa de Input a Select** alimentado por el GET (solo entidades `ica`); opción "— Agregar municipio —" abre el mismo dialog (POST) y selecciona el nuevo. Sin entidades ICA aún → el Select solo ofrece "Agregar municipio". **Elimina el texto libre → mata el typo-duplicado desde la UI.**

### 8.4 Tests (obligatorios — el paquete deja de ser "sin tests backend")
`TestRetentionEntitiesEndpoints`: GET lista estructurada (tipos + municipio parseado + balance) · GET flag-off 403 · POST ICA crea idempotente (dos veces = misma entidad, matching H4 "bogotá"=="Bogotá") · POST retefuente → 422 (solo ica) · RBAC sin permiso → 403 · POST org sin flag → 403. (~6 tests; la suite pasa de 1258 → ~1264.)

### 8.5 Gates del addendum
tsc + build · **suite completa re-run** (ya no "idéntica": +~6 nuevos, cero rojos) · parity check NO aplica (cero migraciones) · golden por-construcción intacto (endpoints flag-gated, orgs prod 403/sin datos) · walkthrough: grupo Pasivos con saldos, pagar desde ahí, agregar municipio, liquidar con Select de municipio.

**Q-08 (nueva, Johana):** ¿necesitan certificados de retención y/o resumen mensual para declaración? → decide la evolución a página dedicada (opción B, ciclo futuro).
