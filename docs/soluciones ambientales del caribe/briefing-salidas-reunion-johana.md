# Briefing — Salidas SAC (reunión Johana, 11-ago 16:00)

Preparado desde la transcripción de las 14:01. Objetivo: cerrar salidas.

---

## 1. Las cuatro salidas y en qué estado están

| Salida | Qué es | Estado real hoy |
|---|---|---|
| **Venta regular** | Plástico, cajas acrílicas, a cliente | ✅ El módulo de ventas existe completo (2 pasos, comisiones, cobro) |
| **Traslado CV → Juan Mina** | Mueve inventario y genera maquila | ✅ **Construido y demostrado hoy** (E3.1): 2 pasos con tránsito, tolerancia, maquila intersede, deuda planta↔circunvalar, kg intersede |
| **Traslado CV → Molino** | Bodega a molino, misma sede | 🟡 El módulo sirve; **falta configurar la ruta de tránsito del molino** (por eso salió "no existe tránsito que rota" en la demo). Es configuración, no desarrollo |
| **Salida a Willard** | Devolver plomo a Willard | 🔴 **No existe.** Es lo único genuinamente nuevo |

**El molino probablemente NO es un módulo nuevo.** Se arma con tres piezas que ya existen:
`traslado CV→Molino` + `transformación` (ya soporta cambio de unidad: entra en unidades, sale en kg,
decisión #53) + `traslado Molino→Juan Mina`. Lo que falta es la **receta preconfigurada** —
qué subproductos salen de qué material— que hoy se captura a mano cada vez.

Conviene no prometer desarrollo nuevo hasta confirmarlo con ella.

---

## 2. Lo que YA quedó decidido hoy (no volver a abrir)

- **Salida Willard resta de DOS cuentas a la vez**: baja lo que SAC le debe a Willard **y** baja lo
  que planta le debe a circunvalar. Postconsumo y drosses son cuentas **separadas** en ambos lados.
- **Molino está en Circunvalar** (no en Juan Mina). Entra por referencia **y** por peso.
- **Molino y CV son un solo inventario conceptual**, separados solo por control — pero **ambos**
  alimentan la deuda de planta con circunvalar.
- **Subproductos de trituración son fijos según lo que entra**: batería normal → plomo fino, plomo
  grueso, lodo (óxido) + PP triturado + jamiche. Batería moto → ABS/acrílico en vez de PP.
- **Green Loop = caja propia**, tratada como caja menor de SAC (igual que la de Yurani): ellos
  pagan y gastan de ahí, SAC les consigna, y solo ven esa caja.
- **Bogotá es un proveedor**, no una sede: Johana no lleva sus proveedores ni sus gastos, solo el
  saldo consolidado.

---

## 3. Lo que hay que cerrar HOY — en orden de impacto

### 🔴 1. Ver sus informes (esto es lo más valioso de la reunión)

Ella misma lo ofreció y tú dijiste que lo necesitabas urgente. **Es el equivalente al Excel de las
entradas, que fue la mejor especificación del ciclo pasado.** Pedirle concretamente:

- El informe **tal como se lo entrega a SAC**, no una descripción.
- Cómo separa circunvalar y planta ("son como dos empresas independientes").
- Dónde aparece la deuda intersede: ella la quiere **como un proveedor más** ("una cuenta por pagar
  a Juan Mina"), y hoy el sistema la presenta como P&L por sede. Son dos presentaciones distintas
  del mismo hecho — hay que ver la suya antes de decidir.

### 🔴 2. La tabla del molino

Pediste que te la mandaran. Sin ella el molino no se puede preconfigurar. Lo que necesitas por cada
material que entra: **qué subproductos salen, en qué unidad, y si hay factor esperado o es 100%
captura manual.** Erwin es el dueño de ese dato, no Johana.

### 🟡 3. Salida a Willard — confirmar la mecánica

Está clara la regla (resta de dos cuentas). Falta:
- ¿La salida sale **siempre** de Juan Mina, o también puede salir de Circunvalar?
- ¿Qué pasa si el plomo a devolver **excede** lo que planta le debe a circunvalar? ¿Se bloquea o
  queda en negativo? (En todo el resto del sistema la regla es **avisar, no bloquear**.)
- ¿Lleva remisión/documento propio, o basta el registro?

### 🟡 4. Consecutivo de remisión

Erwin lo pidió: van en la 15.000. Hoy el campo es libre. Decisión: **¿lo genera el sistema
automáticamente** (y arranca en el número que ellos digan) **o lo siguen digitando?** Si es
automático, hay que definir si es uno solo o uno por sede.

### 🟢 5. Provisionales de Green Loop (puede esperar)

Carlos insistió; Johana dijo que es control interno de ellos. Con la caja propia, un provisional a
un conductor es un **anticipo desde esa caja** — el sistema ya lo soporta sin desarrollo. Vale
confirmarlo, pero no bloquea.

---

## 4. Lo nuevo que salió y hay que dimensionar (no prometer fecha hoy)

- **Green Loop solo ve lo suyo**: acceso a su caja y **solo a las entradas cuyo recolector sea
  Green Loop**. El sistema de permisos hoy filtra por módulo, no por recolector — eso es
  desarrollo nuevo, no configuración.
- **Informe de deuda intersede como cuenta por cobrar/pagar** (punto 1 de arriba).

---

## 5. Dato de configuración pendiente (dev, 2 minutos)

`Circunvalar - Molino` no tiene bodega de tránsito asignada, por eso falló el traslado en la demo.
Las otras dos sí (`Circunvalar - Transito` → Circunvalar, `Juan Mina - Transito` → Juan Mina). Se
resuelve creando el tránsito del molino o ruteándolo al existente, según cómo quieran controlarlo.
