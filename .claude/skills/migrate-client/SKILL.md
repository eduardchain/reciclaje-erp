---
name: migrate-client
description: Migracion de cliente nuevo a EcoBalance — Excel → test en dev → confirmacion → apply en prod
disable-model-invocation: true
allowed-tools: Bash, Read, AskUserQuestion
---

# Migracion de cliente nuevo a EcoBalance

**Proposito:** orquestar el flujo seguro de migracion de un cliente nuevo desde Excel a produccion, con un test obligatorio en dev primero y dos confirmaciones criticas antes de tocar prod.

**Script subyacente:** [backend/scripts/migrate_org.py](backend/scripts/migrate_org.py)
**Template Excel:** [data/migration_template.xlsx](data/migration_template.xlsx)
**Playbook tecnico:** [backend/scripts/MIGRATION.md](backend/scripts/MIGRATION.md)

## Argumentos

- `/migrate-client` — flujo completo, pide todo via AskUserQuestion
- `/migrate-client <ruta-excel>` — toma la ruta como arg, pide el resto

## Filosofia

1. **Dry-run siempre primero** — no escribir nada hasta validar la estructura.
2. **Apply en dev ANTES que prod** — integration test real con balance sheet check.
3. **Dos confirmaciones explicitas antes de prod** — una despues del test dev, otra antes del apply prod.
4. **NUNCA `--reset-org` en prod** — solo en dev. Si el usuario lo pide, refusar y explicar.
5. **NUNCA correr migraciones de schema** — eso es trabajo de `/deploy`. La skill asume schema actualizado.

## Pasos

### 1. Recolectar datos

Si la ruta del Excel no vino como `$ARGUMENTS`, pedirla primero:

```
AskUserQuestion:
  - Cual es la ruta absoluta del Excel del cliente?
```

Luego, con AskUserQuestion en un solo mensaje (4 preguntas paralelas):

- **Nombre de la organizacion** (razon social tal cual aparecera en facturas): texto libre
- **Email del admin del cliente** (el usuario maestro que recibira las credenciales): texto libre
- **Nombre completo del admin** (persona que vera el sistema): texto libre
- **Email del superuser EcoBalance** (la persona con permisos para crear orgs en prod): texto libre (usualmente eduardo.d.chain@gmail.com)

Si el usuario ya dio alguno en el prompt inicial, no preguntarlo de nuevo — leerlo del contexto.

### 2. Pre-flight checks

Verificar requisitos antes de tocar nada:

```bash
# 1. Excel existe y es legible
test -f "$EXCEL_PATH" && echo "OK: archivo existe" || (echo "ERROR: no existe" && exit 1)

# 2. **Verificar que :8000 corra EcoBalance (no otro proyecto)**.
#    Gotcha real: el user puede tener otro uvicorn en :8000 y decir "esta corriendo".
#    Login devolvera 405 inentendible si las rutas son las equivocadas.
lsof -i :8000 | head -3
curl -s http://localhost:8000/health  # debe responder {"status":"healthy"...}
# Si responde "Method Not Allowed" o el lsof no es de reciclaje-erp:
# matar el otro proceso y levantar EcoBalance.

# 3. Migraciones al dia en dev
cd /Users/daniel.chain/Projects/reciclaje-erp/backend && ./venv/bin/alembic current
# Comparar contra heads(). Si difiere: 'alembic upgrade head' antes de continuar.

```

Si cualquiera falla, ABORTAR y reportar al usuario. No continuar.

### 2.5. Auditoria del Excel del cliente (CHECKLIST)

**Paso obligatorio antes del dry-run** — el dry-run del script principal es OFFLINE
y NO atrapa errores de contenido (typos en nombres, jerarquias invalidas, formatos
de fecha, cruces rotos entre hojas, etc.). Esos errores solo aparecen en el apply,
forzando iteraciones costosas con el cliente.

El script `audit_migration_excel.py` los detecta TODOS en plain Spanish:

```bash
cd /Users/daniel.chain/Projects/reciclaje-erp/backend
./venv/bin/python scripts/audit_migration_excel.py "$EXCEL_PATH"
```

**Reglas:**
- Si reporta **errores bloqueantes** (🔴): ABORTAR. Pasarle el reporte al cliente
  para que corrija. NO correr dry-run hasta tener 0 errores.
- Si reporta **warnings** (🟡): revisarlos con el cliente uno por uno. La mayoria
  son legitimos (ej: materiales sin precio, terceros sospechosos como
  'RECICLAJE' que pueden ser materiales mal etiquetados).
- Si todo OK: avanzar al paso 3 (dry-run).

**Que detecta** (lecciones de la migracion de Biogreen 2026-06-23):
- Texto suelto en fila NOTAS que rompe el parser
- Typos en nombres (`Genral` vs `General`, `Resindenciales` vs `Residenciales`)
- Cruces rotos (MapeoUN apunta a categoria que no existe; Inventario.bodega
  apunta a nombre de material en vez de bodega)
- Jerarquia >2 niveles en CategoriaGastos
- Formato de fecha invalido en Inventario (debe ser YYYY-MM-DD)
- Columna `categorias` vacia en Terceros (obligatorio)
- `tipo_comportamiento` invalido en CategoriaTerceros
- Codigos duplicados en Materiales
- Sample rows del template que el cliente olvido borrar (ej: "Bascula Demo")
- Heuristicas: nombres en MAYUSCULAS que parecen materiales en vez de terceros

### 3. Dry-run en DEV (validacion de estructura)

```bash
cd /Users/daniel.chain/Projects/reciclaje-erp/backend
./venv/bin/python scripts/migrate_org.py \
  --file "$EXCEL_PATH" \
  --api-url http://localhost:8000 \
  --org-name "$ORG_NAME" \
  --admin-email "$ADMIN_EMAIL" \
  --admin-name "$ADMIN_NAME" \
  --dry-run 2>&1 | tee /tmp/migration-dryrun-dev.log
```

**Interpretar resultado:**
- Si termina con `DRY-RUN COMPLETADO` → estructura del Excel OK, pasar a paso 4.
- Si termina con `ERROR` → mostrar ultimas 30 lineas del log al usuario, ABORTAR. El cliente tiene que corregir el Excel.

### 4. Apply en DEV (integration test real)

Usar el mismo `org_name` pero con sufijo `_TEST` para diferenciarlo en dev. **Siempre `--reset-org`** para garantizar slate limpio (solo afecta orgs de test en dev, nunca prod).

Pedir password del superuser dev (admin@ecobalance.com):

```
AskUserQuestion:
  - Password del superuser DEV (admin@ecobalance.com)?
```

```bash
TEST_ORG_NAME="${ORG_NAME} TEST"
TEST_ADMIN_EMAIL="test_$(date +%s)@ecobalance.com"

cd /Users/daniel.chain/Projects/reciclaje-erp/backend
./venv/bin/python scripts/migrate_org.py \
  --file "$EXCEL_PATH" \
  --api-url http://localhost:8000 \
  --superuser-email admin@ecobalance.com \
  --superuser-password "$DEV_SUPERUSER_PASSWORD" \
  --org-name "$TEST_ORG_NAME" \
  --admin-email "$TEST_ADMIN_EMAIL" \
  --admin-name "Test Admin" \
  --apply \
  --reset-org 2>&1 | tee /tmp/migration-apply-dev.log
```

**Verificar resultado:**
- Script termina con `MIGRACION COMPLETADA EXITOSAMENTE` y `Balance Sheet diff: $0.00`.
- Si no, mostrar ultimas 50 lineas, ABORTAR, reportar al usuario.

Capturar los counts del reporte final (org_id, terceros, materiales, cuentas, activos fijos, etc.) — los usaremos en el reporte y en el confirm.

### 5. Confirmacion 1 (post-test)

Mostrar al usuario:

```
TEST EN DEV COMPLETADO

Organizacion creada (en dev): {TEST_ORG_NAME}
Org ID: {ORG_ID}
Counts:
  - Categorias terceros: N
  - Materiales: N
  - Terceros: N
  - Cuentas: N (con saldo inicial sumando $X)
  - Activos fijos: N
  - Inventario inicial: N items (valuacion $Y)
Balance Sheet diff: $0.00 ✓
Verificaciones: 9/9 OK

El test en dev fue exitoso. Listo para proceder a PRODUCCION?
```

```
AskUserQuestion:
  question: "El test en dev fue exitoso. Quieres proceder a producir la migracion en PROD?"
  options:
    - "Si, hacer dry-run en prod" (Recommended)
    - "No, cancelar"
```

Si el usuario dice no → ABORTAR limpio. Decirle que la org TEST quedo en dev (org_id) y puede revisarla.

### 6. Dry-run en PROD (validacion contra DB real)

Pedir credenciales prod:

```
AskUserQuestion (2 preguntas):
  - Password del superuser PROD (email ya dado)?
  - Confirmas que el nombre real de la org en prod es: "{ORG_NAME}"?
    Opciones:
      - "Si, ese es el nombre correcto"
      - "No, corregir nombre"
```

```bash
cd /Users/daniel.chain/Projects/reciclaje-erp/backend
./venv/bin/python scripts/migrate_org.py \
  --file "$EXCEL_PATH" \
  --api-url https://api.ecobalance.cc \
  --superuser-email "$PROD_SUPERUSER_EMAIL" \
  --superuser-password "$PROD_SUPERUSER_PASSWORD" \
  --org-name "$ORG_NAME" \
  --admin-email "$ADMIN_EMAIL" \
  --admin-name "$ADMIN_NAME" \
  --dry-run 2>&1 | tee /tmp/migration-dryrun-prod.log
```

**Interpretar:**
- `DRY-RUN COMPLETADO` sin errores → OK, pasar a paso 7.
- Errores tipicos: email del admin ya existe en otra org, nombres de categorias duplicados con seeds defaults, etc. Reportar al usuario, ABORTAR.

### 7. Confirmacion 2 (CRITICA — antes de prod)

Esta es la confirmacion mas importante. Se ejecuta DESPUES de un dry-run prod exitoso, ANTES del apply.

Mostrar resumen final:

```
LISTO PARA APLICAR EN PRODUCCION

Org a crear:           {ORG_NAME}
Admin a crear:         {ADMIN_NAME} <{ADMIN_EMAIL}>
Password inicial:      "123456" (el cliente debera cambiarla en primer login)
API:                   https://api.ecobalance.cc
Entidades a crear:     ~{N terceros} + {N materiales} + {N cuentas} + {N activos}
Inventario:            {N items} con valuacion ${X}

IMPORTANTE:
- Esta operacion CREA datos en PRODUCCION.
- No es reversible automaticamente (el script no tiene --rollback en prod).
- En caso de error, hay que soft-deletar manualmente la org desde /system/organizations.
```

```
AskUserQuestion:
  question: "Confirmas APLICAR esta migracion en PRODUCCION?"
  options:
    - "Si, APLICAR en prod" (NO recommended badge — esto es destructive)
    - "No, abortar"
```

Si no confirma → ABORTAR. Decirle al usuario que el dry-run prod quedo en `/tmp/migration-dryrun-prod.log` por si quiere revisar.

### 8. Apply en PROD

**NUNCA pasar `--reset-org` aca.** Si por error el usuario lo pide, refusar y explicar que reset en prod corromperia la base.

```bash
cd /Users/daniel.chain/Projects/reciclaje-erp/backend
./venv/bin/python scripts/migrate_org.py \
  --file "$EXCEL_PATH" \
  --api-url https://api.ecobalance.cc \
  --superuser-email "$PROD_SUPERUSER_EMAIL" \
  --superuser-password "$PROD_SUPERUSER_PASSWORD" \
  --org-name "$ORG_NAME" \
  --admin-email "$ADMIN_EMAIL" \
  --admin-name "$ADMIN_NAME" \
  --apply 2>&1 | tee /tmp/migration-apply-prod.log
```

**Verificar:**
- `MIGRACION COMPLETADA EXITOSAMENTE` al final.
- `Balance Sheet diff: $0.00` (o dentro de tolerancia).
- `9/9 OK` en checks.

Si falla parcialmente (ej: cae en fase 8 despues de crear categorias y materiales):
- Capturar el org_id parcialmente creado del log.
- Reportar al usuario que la org existe parcialmente en prod.
- Proponer dos opciones: (a) soft-deletar la org desde `/system/organizations` y re-correr; (b) intentar continuar con `--skip-phase` desde donde fallo.

### 9. Cleanup dev (opcional)

Despues del exito en prod, ofrecer borrar la org TEST de dev:

```
AskUserQuestion:
  question: "Migracion en prod exitosa. Quieres borrar la org TEST de dev?"
  options:
    - "Si, soft-delete la org TEST"
    - "No, dejarla para revision"
```

Si si: hacer `DELETE /api/v1/system/organizations/{TEST_ORG_ID}` via curl.

### 10. Reporte final

```
## Migracion COMPLETADA

**Cliente:** {ORG_NAME}
**Admin:** {ADMIN_NAME} <{ADMIN_EMAIL}>
**Password inicial:** 123456 (cambiar en primer login)
**URL de login:** https://app.ecobalance.cc/login

**Datos creados en prod:**
- Org ID: {ORG_ID}
- Categorias terceros: N
- Materiales: N
- Terceros: N
- Cuentas: N (saldo inicial total: $X)
- Activos fijos: N
- Inventario inicial: N items (valuacion $Y)

**Balance Sheet diff:** $0.00 ✓
**Verificaciones:** 9/9 OK

**Logs guardados:**
- /tmp/migration-dryrun-dev.log
- /tmp/migration-apply-dev.log
- /tmp/migration-dryrun-prod.log
- /tmp/migration-apply-prod.log

**Org TEST en dev:** {borrada / conservada en org_id X}

**Proximos pasos:**
1. Entregar credenciales al cliente.
2. Recordarle cambiar la contrasena en primer login.
3. Si tiene operaciones del dia del corte que no estan en el Excel, registrarlas via UI inmediatamente.
```

Si fallo:

```
## Migracion FALLIDA

**Donde fallo:** {fase X — descripcion}
**Estado en prod:** {nada creado / org parcial con id X}
**Estado en dev:** {TEST org creada y verificada / fallo en dev}

**Error:**
{ultimas 20 lineas del log de error}

**Accion requerida:**
{instrucciones de rollback o reintento}
```

---

## Reglas estrictas

1. **Nunca correr `migrate_org.py --apply` contra prod sin pasar primero por dev exitoso.**
2. **Nunca pasar `--reset-org` con `--api-url https://...`.** Si el usuario lo pide, refusar.
3. **Nunca correr `alembic upgrade` desde esta skill.** Si hay migraciones pendientes en dev, abortar y pedir al usuario correrlas manualmente. En prod, las migraciones SOLO se aplican via `/deploy`.
4. **Nunca skipear las dos confirmaciones criticas** (post-test dev y pre-apply prod), incluso si el usuario dice "vai sin preguntar". Estas son las salvaguardas core de la skill.
5. **Si el dry-run prod falla**, NO seguir a apply. El cliente tiene que corregir el Excel o tu tienes que limpiar prod primero.
6. **Logs en `/tmp/migration-*.log`** se conservan toda la sesion para auditoria. No borrar.
7. **Si necesitas editar el Excel programaticamente** (con `openpyxl` desde Python),
   pedile al usuario que **cierre Excel.app primero**. Si el archivo esta abierto
   en la app, cuando el usuario haga Cmd+S sobrescribe tu cambio y se pierde.
   Gotcha real de Biogreen: vacie 31 fechas de Inventario, el user guardo en Excel,
   y mi cambio se perdio — el siguiente apply volvio a fallar con los mismos
   errores. Verificalo con `os.path.getmtime` despues del save.
8. **El dry-run es OFFLINE** (no llama al API). Si el cliente cambia algo despues
   del dry-run, **vuelve a correr la auditoria (paso 2.5) ANTES del apply**, no
   te confies del dry-run anterior.
