# Informe Code — filtro por bodega + descripción por lado del cruce

Pedido de Reciclajes de la Costa (Gustavo Díaz, 2026-10-21). Plan: `plan-filtro-bodega-y-descripcion-cruce.md` v1.2 (grilla de defectos commiteada en `beb0862` antes de plantar). QA: sesión `reciclaje-erp-41`, **GO final 2026-10-21 17:48**. Cero migraciones.

## Qué se construyó

1. **Filtro "Bodega" en Compras y Ventas.**
   - `GET /purchases?warehouse_id=` devuelve las compras con al menos una línea en esa bodega. La bodega vive en la línea (`purchase_lines.warehouse_id`), no en la cabecera: la cabecera es NULL en las 3.173 compras de Costa.
   - El filtro es un `EXISTS` correlacionado. Un join inflaba los totales (900 compras de Costa tienen 2+ líneas en la misma bodega).
   - Ventas ya filtraba por `Sale.warehouse_id`; solo faltaba cablear la pantalla.
   - En pantalla: selector con link directo `?warehouse=` y Excel con el nombre de la bodega en el archivo. El selector exige `warehouses.view`; sin ese permiso no se pide la lista de bodegas, y un link filtrado muestra el chip "Bodega filtrada ×".
2. **Cruce entre terceros con una descripción por lado.**
   - `POST /money-movements/tp-transfer` acepta `destination_description` (opcional, de 1 a 500 caracteres). Si falta, el destino recibe la descripción del origen.
   - El schema gana `extra="forbid"`.
   - Los cruces existentes no se reescriben (decisión de Daniel P1). Las obligaciones (#86) quedan fuera de alcance (P3).
   - Si en pantalla el destino se deja vacío o solo con espacios, viaja como ausente (P2).

## Gates

| Gate | Resultado | Artefacto |
|---|---|---|
| Plantado de defectos | 11/11 en la diagonal de la grilla `beb0862`, restauración verificada por sha256 | `plantado_bodega.log` |
| Suite completa (r1) | **1920 passed**, EXIT=0, 0 FAILED/ERROR/Traceback en todo el log. La predicción (1920) se escribió antes de lanzar: `git diff f745eb1..HEAD -- backend/tests` vacío + 12 nuevos. mtime 0 con control positivo de 660. Duró 3:51:27 por contención de CPU en Docker con contenedores de otros proyectos | `suite_bodega_r1.log` |
| C6 (después de la r1) | El árbol = el de la r1 + 1 línea, por reconstrucción del hash (reproducida por QA). Tests que leen `frontend/src`: 67 passed. tsc 0. eslint 37 (= techo). Build OK | `c6_verificar.log`, `c6_reconstruccion.log` |
| Paso 3 (C3, permisos) | Chrome headless por CDP con control positivo: sin `warehouses.view` no hay selector ni `GET /warehouses`; con el permiso, sí | `paso3_cdp.log`, `paso3/*.png` |
| Subset de QA (independiente) | 210 passed en 23:13, EXIT=0, predicción escrita antes (collect-only). TREE `f32c42a1c5171c6d` al arrancar y al terminar. Cubre el archivo nuevo + `test_api_money_movements.py` + `test_financial_obligations.py`, los dos que llaman a `/tp-transfer` y ahora pasan por `forbid` | log de QA (`qa_subset_bodega.log`) |
| Pantalla (Daniel) | Filtro y cruce, C6, destino con solo espacios, Excel con la bodega, Ventas a 390 px: OK | — |
| Golden | No aplica: `/purchases`, `/sales` y `POST /tp-transfer` no están en CAPTURES. `/money-movements/third-party/{id}` sí está, pero no cambia ningún código que lo construye ni se reescriben filas existentes | — |

## Huecos encontrados en el camino

- **T9/T10 vacuos.** El estado de cuenta muestra los últimos 90 días por defecto y la fecha del test quedaba fuera, así que los `== []` pasaban sin mirar nada. Ahora usan `date_from` explícito y tienen control positivo.
- **TypeScript no revisa las propiedades de más dentro de un spread.** Esto compila: `...(c ? { clave_mal_escrita: x } : {})`. Lo medí plantando la clave mal escrita. Por eso el payload usa una propiedad directa.
- **C6 (QA).** `resetFields` no limpiaba la descripción del destino al cambiar de tipo.
- **Guía de pantalla.** El usuario de prueba con correo `@local.test` no podía entrar por la pantalla: `/auth/login/json` valida con `EmailStr`, que rechaza los dominios especiales. Mi "login OK" lo había medido contra `/auth/login` (formulario), que no valida el correo. Corregido a `@example.com`.

## ⚠️ Datos de prueba que existen SOLO en dev (5434)

En la org Costa de dev hay dos usuarios y dos roles **de prueba**. No son datos del cliente y desaparecen con el próximo `replicate_prod.sh`:

- `prueba.sinbodegas@example.com`, rol "PRUEBA sin bodegas (dev)": ve Compras y Ventas sin `warehouses.view`.
- `prueba.conbodegas@example.com`, rol "PRUEBA con bodegas (dev, control positivo)": el mismo rol más `warehouses.view`.

Los artefactos (`*.log`, capturas) viven en el scratchpad de la sesión: son evidencia de la corrida, no del repositorio.
