# Plan de Ejecución Fase 1 — SAC

Versión 1.0 — 2026-07-15. Base: requerimientos-funcionales.md v0.5 (§16.1) + propuesta comercial v1.5 FINAL ACORDADA ($12M en hitos 3.6/3.6/4.8 + $1.5M/mes). Contrato firmado; primer hito se paga 2026-07-16 → ese pago activa la semana 0.

**Los tres principios de este plan:**

1. **Cero regresión sobre lo construido** — 3 empresas operan en productivo. Es el gate #1 de cada entrega, por encima de cualquier fecha.
2. **Entregas funcionales semanales** — SAC recibe módulos usables cada viernes, prueba e itera sobre su propia organización desde el día 1.
3. **Lo recibido manda** — el feedback de SAC se tría cada semana: bug (se corrige ya), ajuste de alcance v0.5 (se hace), mejora nueva (backlog → bolsa mensual post go-live).

---

## 1. Estrategia de no-regresión (el sanity check #1)

### 1.1 Regla arquitectónica: aditivo y apagado por defecto

| Tipo de cambio | Regla |
|---|---|
| Tablas nuevas (KgLedger, ServiceTariff, InboundOrder, etc. — 12 en total) | Sin restricción: no las toca nadie más. Riesgo cero |
| Columnas en tablas existentes (`warehouse_id` en MoneyMovement/MoneyAccount, `willard_*` en Sale, etc.) | **Siempre NULLABLE con default NULL**. Cero backfill, cero cambio de semántica. Una fila vieja se comporta idéntico con la columna en NULL |
| Tipos de movimiento nuevos (`internal_maquila_expense/income`, etc.) | Aditivos al enum. Los reportes existentes NO los suman por diseño (filtran por lista explícita de tipos) — verificar con test, no asumir |
| Flujos compartidos modificados (traslado dos pasos, liquidación con descarga de cuenta kg) | **Feature flag por organización** en `organization.settings` JSONB (§11.2.8 del doc técnico): `kg_ledger_enabled`, `two_step_transfers_enabled`, `internal_maquila_enabled`. Default `false` → las 3 empresas actuales ejecutan EXACTAMENTE el código de hoy. SAC nace con los flags en `true` |
| Migraciones Alembic | Solo CREATE TABLE / ADD COLUMN nullable / valores de enum. **Prohibido**: RENAME, DROP, ALTER de tipo, backfills que cambien datos existentes. Toda migración debe poder correr en una BD de producción viva sin tocar una sola fila existente |

### 1.2 Gates obligatorios por entrega (checklist, en orden)

1. **Suite completa verde** (~1131 tests actuales + los nuevos — el número crece con cada entrega; el criterio es CERO fallos, no un número) — no "los tests del módulo": TODA la suite, en la BD de test (5433). Los 6 fallos "pre-existentes conocidos" quedaron resueltos el 2026-07-15 (paquete #73): ya no existe la categoría "fallo conocido tolerado" — cualquier test rojo es hallazgo.
2. **Golden comparison contra réplica de producción**: `./scripts/replicate_prod.sh` → capturar P&L del mes corriente, Balance General y saldos de cuentas de 2-3 orgs reales ANTES del cambio → aplicar migraciones + código → volver a capturar → **diff debe ser exactamente cero**. Es la prueba directa de "no le cambié nada a nadie".
3. **QA aprobado antes del commit** (regla vigente del proyecto: QA gate antes de commit local, no solo antes de push).
4. Commit a `develop`, nunca directo a `main`. Deploy a producción SOLO via `/deploy` (merge a main incluido).
5. Migraciones corridas en dev (5434) Y test (5433) antes de probar — los permisos RBAC nuevos viven en la tabla `permissions`, sin migrar no existen.

### 1.3 Coordinación con el trabajo en curso (validado 2026-07-15 contra git y memoria)

- ✅ **Bug del costo promedio móvil: RESUELTO Y EN PRODUCCIÓN** — paquete Modelo L PR-1→PR-5 (decisiones #63-#66), deploy `deploy-2026-07-10-1222` (main `851160e`, 6 migraciones limpias). SAC arranca sobre el modelo corregido ("nada existe financieramente hasta que se liquida" — alineado además con la liquidación manual de Johana). **Consecuencia: desaparece el único cambio de lógica compartida previsto — este proyecto queda 100% aditivo.**
- ✅ **Features Costa A/A.2** (Rentabilidad UN + % generales): en main, deployadas el 10-jul.
- ✅ **Lote Costa pendiente: CERRADO (2026-07-15)** — todo el backlog de develop quedó mergeado y deployado a prod: Obligaciones Financieras (PR #6, deploy-2026-07-14-1650), fletes/bonos (PR #7), P&L por rubros + placa/cantidad (PR #8), paquete #73 (PR #9, deploy-2026-07-15-2322). `develop` quedó detrás de `main` → el primer paso de E1 es fast-forward. **El deploy de E1 no arrastra migraciones ajenas.**

---

## 2. Desglose en entregas funcionales

Mapa de los 18 módulos del §16.1 a 6 entregas semanales. Cada una termina en **demo de viernes + guion de pruebas** para que SAC pruebe la semana siguiente.

### Entrega 0 — "Las llaves" (semana 0, 1-2 días tras el pago)

- Crear organización SAC en producción (vía `/system/organizations`).
- 6 bodegas: CV, JM, BOG + virtuales CV-MOLINO, JM-TRANSITO, CV-TRANSITO.
- Usuarios reales con roles estándar provisionales (Johana=admin, David=bascula, etc.); los 10 roles SAC finos llegan en la entrega 5.
- Maestros mínimos: categorías de materiales, materiales principales (baterías, plomo crudo, drosses SEC, retal…), cuentas de dinero, categorías de gasto base.
- **SAC ya puede entrar**: el 75-80% del producto (compras, ventas, tesorería, inventario, reportes) ya existe y funciona. Que Johana y David hagan operaciones de juguete esta semana — familiarización temprana = capacitación gratis y feedback de UX antes de construir nada.
- Datos de esta etapa son de PRUEBA: antes del corte se limpia todo con `/migrate-client --reset-org` (diseñado exactamente para esto).

### Entrega 1 — "Configuración SAC" (fin semana 1)

- Modelo de datos completo (12 tablas nuevas, migraciones aditivas) + org settings JSONB con flags.
- ServiceTariff CRUD (maquila $2.097, flete planta $37, flete BOG-BAQ $216, maquila interna $1.500/$300 — **sugeridos y parametrizables**).
- Fórmulas de conversión (plomo equivalente, SEC escurrido/pinza), conductores y vehículos.
- **SAC prueba**: Johana carga y valida las tarifas y factores reales.

### Entrega 2 — "Cuentas en kilogramos" (fin semana 2)

- KgLedger: 5 cuentas (Willard baterías con sub-saldos BAQ/BOG, drosses, intersede, horno, crisol) + movimientos + tolerancias.
- Recepción unificada (InboundOrder): chatarra, postconsumo y drosses en una sola pantalla, por sede.
- Compras con liquidación manual de Johana conectadas a cuenta kg.
- **SAC prueba**: entrada de postconsumo en CV → la cuenta Willard se mueve sola; entrada de drosses por JM; compra propia que NO toca cuenta kg hasta liquidar.

### Entrega 3 — "Maquila y planta" (mitad semana 3)

- Traslados dos pasos (despacho → recepción confirmada, tolerancia 3-5%, diferencias al panel).
- Par de maquila interna CV→JM al confirmar recepción + cargo de crisol a la salida.
- Transformaciones conectadas a cuentas kg (molino, horno con retal como insumo, crisol).
- **SAC prueba**: traslado CV→JM completo; ver el gasto en CV y el ingreso en JM; fundir y sacar plomo crudo.

### Entrega 4 — "Willard completo" (fin semana 3)

- Despachos a Willard con remisión, cargo de maquila + flete POR ENTREGA (CxC causada, cobro aparte).
- Factura mensual de flete BOG-BAQ (idempotente).
- Conciliación semanal de viernes: reporte por cuenta con detalle por entrega (fecha, remisión, kg), firma del coordinador.
- **SAC prueba**: simular una semana Willard completa y cuadrar el viernes contra un corte real histórico que Johana tenga a mano.

### Entrega 5 — "Control total" (fin semana 4, en paralelo con migración)

- Panel de excepciones (diferencias fuera de tolerancia, sin liquidar al cierre, arqueos, kg físico vs cuenta, tránsito >48h) + sello diario OK.
- Dashboard SAC + P&L por sede + consolidado (excluye tipos internos) + reportes SAC restantes.
- RBAC fino: 15 permisos nuevos + los 10 roles definitivos (Yurani por cajas asignadas, Erwin auditor, comercial DP, coordinador postconsumo).
- **SAC prueba**: un día completo de operación simulada terminando con panel vacío y sello OK.

### Semanas 4-8 — según cronograma contractual

- **S4**: migración de datos reales (template extendido con 3 hojas: cuentas kg, tarifas, fórmulas; dry-runs con Johana; `--reset-org` para limpiar las pruebas).
- **S5**: UAT remota integral con guion basado en los criterios de aceptación §2.7.
- **S6**: semana presencial Barranquilla — capacitación por rol, corte VIERNES, go-live.
- **S7**: operación en paralelo, acompañamiento diario, panel de excepciones como termómetro.
- **S8**: verificación de criterios + cierre + **hito 3 ($4.8M)** → arranca mensualidad.

---

## 3. La dinámica semanal (cómo iteramos con SAC)

| Día | Qué pasa |
|---|---|
| Lunes-jueves | Desarrollo del módulo de la semana. SAC prueba lo entregado el viernes anterior con su guion |
| Durante la semana | Feedback por el canal acordado (WhatsApp/grupo). Triage: **bug** → se corrige en la misma semana; **ajuste dentro del alcance v0.5** → se hace; **idea nueva** → backlog para la bolsa mensual (se registra, no se pierde, no frena) |
| Viernes | Deploy (con los 5 gates del §1.2) + demo corta (15-30 min, remota) + entrega del guion de pruebas siguiente + cierre semanal con Hugo (avance vs cronograma) |

**Reglas de la dinámica**: (a) el guion de pruebas le dice a SAC exactamente qué mirar — sin guion, el cliente prueba caóticamente y el feedback llega tarde; (b) toda idea nueva se ANOTA y se agradece, pero el alcance de Fase 1 es el doc v0.5 — el backlog alimenta la bolsa de 12 h/mes desde la semana 9, que para eso está; (c) si una semana no hay demo que mostrar, se dice y se recupera — nunca demo de humo.

---

## 4. Riesgos operativos de este plan

| Riesgo | Mitigación |
|---|---|
| Deploy semanal a prod expone a las 3 empresas a código nuevo | Flags apagados por defecto + gates §1.2 (suite completa + golden comparison). El código dormido no ejecuta |
| Feedback de SAC infla el alcance en caliente | Triage explícito §3; el backlog → bolsa mensual |
| ~85 h/semana de dev en S1-3 (factor 0.6×) | Congelar soporte no-urgente de otros clientes en S1-3; colchón = S5 de UAT; el corte viernes puede correrse 1 semana sin tocar hitos |
| Migración de Johana sucia | Dry-runs desde S4 temprano, tolerancias configurables, `--reset-org` ya probado en 4 migraciones |
| ~~El lote pendiente de develop se mezcla con el primer deploy SAC~~ | **RESUELTO 2026-07-15**: lote Costa deployado completo antes de E1 (§1.3) — el primer deploy SAC sale limpio |

---

## 5. Ciclo de trabajo por entrega (way of work acordado 2026-07-15)

Cada entrega E1-E5 recorre este ciclo completo:

1. **Plan** (Code): `docs/planes/plan-sac-eN-<nombre>.md` — siguiendo la convención del repo. Formato QA-revisable: contratos (endpoints, schemas, migraciones), invariantes de negocio, lista de tests planeados, sección explícita de **no-regresión** (qué flags, qué columnas nullable, alcance del golden comparison) y criterios de done.
2. **Revisión del plan** (agente QA de Daniel): comentarios.
3. **Respuesta** (Code): corrige, o **refuta con argumentos** — el derecho a refutar es parte del diseño del ciclo. Itera hasta el GO de QA.
4. **Código** (Code, SOLO con el go de QA): implementación + tests + build.
5. **Informe a QA** (Code): qué se hizo vs el plan, desviaciones, y **evidencia** — suite completa verde, diff del golden comparison en cero, migraciones corridas en dev (5434) y test (5433).
6. **Pruebas manuales** (Daniel) → **GO de Daniel** → commit a `develop` (regla vigente: QA + pruebas manuales ANTES del commit, no solo antes del push).
7. **Viernes**: deploy vía `/deploy` + demo a SAC + guion de pruebas.

**Reglas del ciclo:**

- **Desviación menor** durante la implementación (no toca contratos, migraciones ni flags) → se documenta en el informe del paso 5 y se sigue. **Desviación mayor** → vuelve a QA antes de continuar. Sin esta distinción, o se re-litiga todo (parálisis) o se desvía en silencio (peor).
- **Ciclos solapados para sostener la cadencia semanal**: mientras QA revisa el plan de E(n+1), se codifica E(n) ya aprobada. El ciclo 100% secuencial consume 2-3 de los 5 días hábiles y mata el viernes.
- **Desempate**: si QA y Code no acuerdan tras una ronda de refutación, decide Daniel. Autoridad de diseño explícita, sin ping-pong infinito.
