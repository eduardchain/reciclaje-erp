# EcoBalance — Migracion inicial de cliente

Este playbook documenta como migrar los datos maestros de un cliente nuevo a una nueva instancia de EcoBalance via el script `migrate_org.py` + template `migration_template.xlsx`. Solo carga maestros + saldos iniciales — NO operaciones historicas.

## Prerequisitos

- **Acceso superuser** al sistema EcoBalance (para crear org via `/system/organizations`).
- **Backend deployado** con todas las migraciones aplicadas (`alembic upgrade head`).
- **Excel del cliente** con datos en `migration_template.xlsx` llenado segun specs (ver "Hoja por hoja").
- **BD limpia** (si no es la primera org de la instancia, basta con que el nombre de la org no choque).
- **Backup completo** de la BD destino antes de un `--apply` en produccion.

## Flujo

1. **Dry-run sin --apply** — valida sin tocar la BD ni requerir login:
   ```bash
   ./venv/bin/python3 scripts/migrate_org.py \
     --excel <path/al/excel.xlsx> \
     --org-name "<Nombre del cliente>" \
     --admin-email <email>
   ```
2. **Revisar warnings/errors** en el output. `Errores: 0` es prerequisito para apply.
3. **Aplicar** (requiere superuser + confirmacion manual):
   ```bash
   ./venv/bin/python3 scripts/migrate_org.py \
     --excel <path> \
     --org-name "<Nombre>" \
     --admin-email <email> \
     --admin-name "<Nombre del admin>" \
     --superuser-email <super>@ecobalance.com \
     --superuser-password '<pwd>' \
     --apply
   ```
4. **Verificacion automatica** corre al final: conteos exactos + sumas con tolerancia (default $100, ajustable con `--balance-tolerance`) + Balance Sheet `is_balanced == true`. Si algun check falla, exit code 1 con dump del diff.
5. **Verificacion manual UI** (~15 min): login con el admin user, validar Balance Sheet, conteos de entidades en cada modulo, una compra de prueba que descuenta stock y mueve balances.

Para apply en produccion, el script se corre **localmente apuntando al api-url remoto** (`--api-url https://api.ecobalance.com`), nunca desde el VPS.

## Hoja por hoja (referencia detallada)

El template tiene **12 hojas**. Orden de carga (importante por FKs): UnidadesNegocio → Bodegas → CategoriaMateriales → CategoriaGastos → CategoriaTerceros → Materiales → Precios → Terceros → Cuentas → Inventario → ActivosFijos. `MapeoUN` es solo referencia.

### 1. UnidadesNegocio

Cargar **primero** — referenciada por Materiales, CategoriaGastos y ActivosFijos.

| Columna | Notas |
|---|---|
| `nombre`* | Unico por org |
| `descripcion` | Opcional |
| `is_active` | Default `true` |

### 2. Bodegas

| Columna | Notas |
|---|---|
| `nombre`* | Unico por org |
| `descripcion`, `address` | Opcionales |
| `is_active` | Default `true` |

Si la hoja viene vacia, el script crea fallback: una sola bodega `Principal`.

### 3. CategoriaMateriales

| Columna | Notas |
|---|---|
| `nombre`* | Unico por org |
| `descripcion` | Opcional |

### 4. CategoriaGastos

Soporta jerarquia 2 niveles (padre → hija). Subcategoria hereda `es_directo` del padre, dejar la columna vacia en filas hijas. **Carga en 2 passes**: primero raices, luego hijas resolviendo `padre` por nombre.

| Columna | Notas |
|---|---|
| `nombre`* | Unico por padre |
| `padre` | Vacio = raiz |
| `es_directo` | `SI`/`NO`, default `NO`. Solo en raiz. |
| `asignacion_un` | `directo` \| `compartido` \| `general`. Default `general`. |
| `unidad_negocio` | Asignacion simple (FK UnidadesNegocio) |
| `unidades_negocio` | CSV para asignacion multiple (compartido) |
| `descripcion` | Opcional |

### 5. CategoriaTerceros

**No duplicar las 7 categorias default** (`Proveedor Material`, `Proveedor Servicios`, `Cliente`, `Socios`, `Generico`, `Provision`, `Pasivo`) — se siembran automaticamente al crear la org. Esta hoja es para categorias **extras** del cliente (ej: `Obligaciones Financieras` con `tipo_comportamiento=inversionista`).

Soporta jerarquia 2 niveles. `tipo_comportamiento` solo en raices (hijas lo heredan).

| Columna | Notas |
|---|---|
| `nombre`* | Unico por padre |
| `tipo_comportamiento` | `proveedor_material`, `proveedor_servicios`, `cliente`, `inversionista`, `generico`, `provision`, `pasivo`. Solo en raices. |
| `padre` | Vacio = raiz |
| `descripcion` | Opcional |

### 6. MapeoUN (referencia, no escribe)

Tabla auxiliar que el script consulta como **fallback** cuando una fila de `Materiales` no especifica `unidad_negocio` propia. Util para evitar repetir la UN en cada material.

| Columna | Notas |
|---|---|
| `categoria_material`* | FK CategoriaMateriales |
| `unidad_negocio_default`* | FK UnidadesNegocio |
| `notas` | Opcional |

### 7. Materiales

| Columna | Notas |
|---|---|
| `codigo`* | Unico por org |
| `nombre`* | |
| `categoria`* | FK CategoriaMateriales |
| `unidad_negocio` | FK UnidadesNegocio. Si vacio, fallback a MapeoUN por categoria. |
| `unidad` | `kg` \| `ton` \| `unit`. Default `kg`. |
| `descripcion` | Opcional |

Stock y costo arrancan en 0 — se siembran via hoja `Inventario`.

### 8. Precios

Por cada fila, el script hace **2 POSTs separados** a `/api/v1/price-lists/` (uno tipo `purchase`, uno tipo `sale`). `notas` se pasa a ambos. Filas con ambos precios vacios o 0 se omiten.

| Columna | Notas |
|---|---|
| `material_codigo`* | FK Materiales |
| `precio_compra` | Decimal. 0/vacio = no crear precio compra. |
| `precio_venta` | Decimal. 0/vacio = no crear precio venta. |
| `notas` | Opcional, va a ambos POSTs. |

### 9. Terceros

`saldo_inicial`: positivo = "nos debe" (cliente que no ha pagado, anticipo a proveedor), negativo = "le debemos" (proveedor con factura pendiente). Setea `current_balance = initial_balance` al crear el tercero — **no genera MoneyMovements de apertura**.

| Columna | Notas |
|---|---|
| `nombre`* | Unico por org |
| `identificacion` | Opcional |
| `email`, `telefono`, `direccion` | Opcionales |
| `categorias`* | CSV M:N. Nombres exactos de CategoriaTerceros (defaults o extras). |
| `saldo_inicial` | Default 0. Signo segun convencion arriba. |
| `provision_type` | Solo si el tercero tiene categoria `Provision` |

### 10. Cuentas

| Columna | Notas |
|---|---|
| `nombre`* | Unico por org |
| `tipo`* | `efectivo` → `cash`, `banco` → `bank`, `digital` → `digital` |
| `saldo_inicial` | `>= 0` obligatorio. Sobregiros se modelan como ThirdParty categoria `Pasivo`. |
| `numero_cuenta`, `banco` | Opcionales |

### 11. Inventario

Siembra stock por bodega via `POST /api/v1/inventory/adjustments/increase` con `reason="Carga inicial migracion {org_name}"`. **Este reason es el marker (decision #28)** que excluye los seeds del `adjustment_net` en `_calculate_profit` — el inventario inicial es patrimonio absorbido por los socios, NO ganancia operativa.

| Columna | Notas |
|---|---|
| `material_codigo`* | FK Materiales |
| `bodega`* | FK Bodegas (default `Principal` si la hoja Bodegas estaba vacia) |
| `cantidad`* | Decimal |
| `costo_unitario`* | Decimal. Siembra `MaterialCostHistory` para costo promedio. |
| `fecha` | Opcional. Llena `MaterialCostHistory.transaction_date` para Balance Detallado historico (decision #41). |

### 12. ActivosFijos

`depreciation_rate` se calcula como `100 / vida_util_meses` (vehiculos 60, maquinaria 120, herramientas 36). La columna antigua `tasa_depreciacion` NO existe en este template.

**Modo `historical_load` (decision #46)**: si `proveedor` Y `cuenta_pago` estan **ambos vacios** → el activo se carga con `historical_load=True` (no genera MoneyMovement, no afecta balances de cuenta ni proveedor). Usar para activos pre-sistema cuyo pago ya ocurrio en el ERP origen.

| Columna | Notas |
|---|---|
| `nombre`* | |
| `codigo_activo` | Opcional |
| `fecha_compra`* | |
| `fecha_inicio_depreciacion`* | |
| `valor_compra`* | Decimal |
| `valor_residual` | Default 0 |
| `vida_util_meses`* | Entero |
| `depreciacion_acumulada` | Default 0. Validacion: `<= valor_compra - valor_residual`. |
| `categoria_gasto`* | FK CategoriaGastos |
| `proveedor` | FK Tercero. XOR con `cuenta_pago`. Crea `asset_purchase`. |
| `cuenta_pago` | FK Cuenta. XOR con `proveedor`. Crea `asset_payment`. |
| `unidad_negocio` | UN simple (FK UnidadesNegocio) |
| `unidades_negocio` | CSV → `applicable_business_unit_ids` |
| `notas` | Opcional |

## Entidades seedeadas automaticamente con la org (NO incluir en Excel)

Al crear la org via `POST /api/v1/system/organizations`, el backend ya siembra:

- **5 roles de sistema**: `admin`, `bascula`, `liquidador`, `planillador`, `viewer`.
- **7 categorias default de ThirdParty**: `Proveedor Material`, `Proveedor Servicios`, `Cliente`, `Socios`, `Generico`, `Provision`, `Pasivo`.
- **71 permisos** (catalogo global, M:N con roles via `role_permissions`).
- **Usuario admin** con el email/nombre del flag `--admin-email`. Password default `123456` (cambiar en UI en primer login).

## Re-ejecucion (idempotencia) y --reset-org

`migrate_org.py` es **idempotente para datos maestros**: si una entidad ya existe (HTTP 409 o match por nombre/codigo), se omite sin error. Se puede re-correr las veces necesarias.

**Limitacion**: `initial_balance` de cuentas y terceros NO se actualiza en re-corridas — solo se setea al crear. Si despues de un apply parcial detectas saldos incorrectos **pre go-live**, usar:

```bash
./venv/bin/python3 scripts/migrate_org.py [...] --apply --reset-org
```

`--reset-org` soft-deletea (`is_active=False`) la org existente antes de re-aplicar limpio. **Solo viable pre go-live**, mientras nadie esta operando. Post go-live, las correcciones se hacen via UI/API, NO via re-corrida.

### Skip de phases

```bash
--skip-phase 11,12
```

Util para no resemilla stock ni activos cuando ya estan cargados:

| # | Phase |
|---|---|
| 1 | Org + admin |
| 2 | UnidadesNegocio |
| 3 | Bodegas |
| 4 | CategoriaMateriales |
| 5 | CategoriaGastos |
| 6 | CategoriaTerceros |
| 7 | MapeoUN (referencia, no escribe) |
| 8 | Materiales |
| 9 | Precios |
| 10 | Terceros |
| 11 | Cuentas |
| 12 | Inventario |
| 13 | ActivosFijos |

## Verificacion post-load

Corre automaticamente al final del `--apply` (si no se uso `--skip-phase`):

| Check | Tolerancia |
|---|---|
| `count(materials)` >= filas en hoja Materiales | exacto |
| `count(third_parties)` >= filas en hoja Terceros (defaults no cuentan) | exacto |
| `count(fixed_assets)` == filas en hoja ActivosFijos | exacto |
| `sum(money_accounts.balance)` == suma `saldo_inicial` hoja Cuentas | `--balance-tolerance` (default $100) |
| `sum(fixed_assets.current_value)` == suma `valor_compra - depreciacion_acumulada` | `--balance-tolerance` |
| Balance Sheet `is_balanced == true` | tolerancia incluida en el endpoint |

Si el corte tiene operaciones del dia que no estan en el snapshot del ERP origen (ej: un arriendo del mismo dia del go-live), correr con `--balance-tolerance` alto y registrar esos movimientos via UI **inmediatamente despues** del `--apply` para volver a cuadrar.

## Notas tecnicas

- **Decision #28 (reason marker)**: ajustes de inventario creados durante la migracion llevan `reason="Carga inicial migracion {org}"`. `_calculate_profit` los excluye del `adjustment_net` para que no inflen la Utilidad Acumulada. NO cambiar este string sin actualizar tambien `services/reports.py`.
- **Decision #46 (historical_load)**: activos fijos sin `proveedor` ni `cuenta_pago` activan modo `historical_load=True` → no se genera MoneyMovement, balances de origen permanecen intactos. Validacion adicional client-side: `depreciacion_acumulada <= valor_compra - valor_residual`.
- **Decision #47 (Socios)**: el seed default usa `Socios` (NO `Inversionista`). Compatible con el filtro de repartibles `ILIKE '%socio%'` de `ProfitDistribution`. Categorias extras tipo `Obligaciones Financieras` con `tipo_comportamiento=inversionista` quedan agrupadas bajo "Inversionistas" en Balance Detallado, sub-agrupadas por nombre de categoria.
- **Balance historico pre-corte**: para consultas `as_of_date < go-live`, el sistema usa el fallback de costo de decision #41 (`MaterialCostHistory` mas reciente <= corte). Inventario pre-corte se ve con costo del seed, no con costo promedio "real" del ERP origen — comportamiento aceptado, el go-live es el punto cero contable.

## Apendice: caso MetaRecycling (referencia historica)

La migracion del primer cliente de produccion (origen: plataforma Lovable/Supabase) fue el caso fundacional que motivo:

- **Decision #28**: reason marker para excluir seeds del P&L.
- **Decision #46**: `historical_load` en activos fijos para no inventar MoneyMovements de pago ya ocurridos en el sistema origen.
- **Decision #47**: rename `Inversionista` → `Socios` en seed default para alinear con filtro de repartibles.
- **Patron "obligacion financiera como tercero"**: deuda bancaria pre-existente se cargo como `ThirdParty` con categoria custom `Obligaciones Financieras` (`tipo_comportamiento=inversionista`) en vez de como `MoneyAccount` con saldo negativo. Balance Detallado la ubica en seccion `Obligaciones Financieras` dentro de Inversionistas (no en Pasivos) por convencion con otras orgs del mismo nicho.
- **Patron Excel armado por AI del sistema origen**: el cliente entrego el template `migration_template.xlsx` a la AI del ERP origen, que consulto la base de datos y llenado las 12 hojas. Mas confiable que transcripcion manual cuando hay decenas de materiales y cientos de terceros.

Este apendice se mantiene como apunte historico — los detalles operativos del caso (BD especifica, cuentas concretas, usuarios) viven en el repo privado del cliente y no aplican a futuras migraciones.
