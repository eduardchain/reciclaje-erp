# Acta — Entrega 0 (bootstrap SAC en producción)

**Fecha:** 2026-07-16 · **Ejecutado por:** Code (script `e0-bootstrap-sac.py`, solo vía API — cero acceso directo a BD)
**Disparador:** primer hito pagado (2026-07-16).

## Resultado

| Entorno | Org ID | Estado |
|---------|--------|--------|
| Producción (`api.ecobalance.cc`) | `db95c7c1-fe0d-4a21-adfa-75cc60162ae6` | 50/50 creados, 0 errores |
| Dev (`localhost:8000`, ensayo) | `93454abb-bfcd-46c7-a7db-b47877c066d1` | Completo — **se conserva** como org de trabajo para desarrollo de E1 |

## Usuarios (rol `admin` de la org — NO superuser de sistema)

| Usuario | Password temporal | Nota |
|---------|-------------------|------|
| johana@sac.com | `123456` (default del endpoint de sistema) | Admin inicial de la org |
| hugo@sac.com | `Sac2026*cambiar` | Registrado + agregado como admin |

Ambos **deben cambiar su password al primer ingreso** (menú usuario → Cambiar contraseña). URL: https://app.ecobalance.cc

## Maestros sembrados (verificados con login de ambos usuarios)

- **6 bodegas:** Circunvalar, Juan Mina, Bogota (físicas) + Circunvalar - Molino, Juan Mina - Transito, Circunvalar - Transito (virtuales).
- **4 UN:** UN1 Reciclaje Plomo, UN2 Maquila Willard, UN3 Reventa DP, UN4 Proyectos Especiales (+ "Pasa Mano" de sistema, seed automático).
- **19 materiales** en 4 categorías — unidades del Anexo C verificadas: 7 baterías (`BAT-*`) en **unidad**, 12 (drosses/chatarra/producto) en **kg**. Prerequisito de las fórmulas de conversión de E1 (D11c).
- **4 cuentas** en $0: Caja Circunvalar, Caja Juan Mina, Caja Bogota, Banco Principal.
- **8 categorías de gasto** (3 directas: Transporte y Fletes, Combustibles, Insumos de Planta).
- **3 terceros de PRUEBA** (proveedor / cliente / transportador). Prefijo `PRUEBA - ` deliberado.

## Advertencias vigentes

- **Todo dato de negocio que SAC capture antes del corte es de juguete**: la semana 4 (S4) se limpia con `/migrate-client --reset-org` antes de la carga real de saldos.
- Los usuarios son admin **de la org SAC** únicamente; se pidió "superadmin" y se interpretó como admin de org — un superuser de sistema vería las otras 3 empresas (inaceptable). Flag levantado a Daniel en su momento.
- El script es **resume-safe** (`E0_RESUME=1` salta lo ya existente por nombre/código) — así se recuperó el aborto parcial del ensayo dev (405 por path `/materials/categories` → correcto: `/material-categories`).
