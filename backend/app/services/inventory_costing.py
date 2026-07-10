"""
Costeo de inventario con conservacion de valor (Modelo L, decision #65).

Helper PURO (sin DB) que centraliza la incorporacion de unidades al pool
liquidado de un material. Reemplaza las ramas "reset" que borraban valor
cuando el pool estaba negativo (oversell):

- Antes: `if old_liquidated <= 0: avg = confirmed_price` descartaba el valor
  del hueco — el COGS ya cargado a las ventas del oversell quedaba sin
  contrapartida y la diferencia contra el costo real de reposicion se
  esfumaba (ni inventario ni P&L). Ver plan seccion 4,
  docs/planes/plan-fix-estructural-costo-promedio.md.

- Ahora: el hueco se "cierra" al costo real de lo que entra y la diferencia
  se retorna como `cost_adjustment` para que el caller la persista y el P&L
  la reconozca ("Ajuste de costo por sobreventa").

Callers de incorporate_into_pool: liquidacion de compra (purchase.py, con el
costo AJUSTADO por comision — G1), cancelacion de venta liquidada (sale.py,
reingreso ponderado al COGS historico), ajuste increase y destinos de
transformacion (PR-4), y desde Fase 5 los reingresos de reversiones (annul
de decrease/zero_out/recount-negativo, fuente de transformacion anulada).

remove_from_pool (Fase 5, plan docs/planes/plan-fase5-remocion-ponderada.md)
es el espejo: saca del pool lo que una operacion revertida habia metido, al
costo con que entro. Reemplaza el rewind via MaterialCostHistory
(revert_cost_change), que era exacto SOLO si nada extrajo valor del pool
entre la operacion y su reversion — bajo Modelo L las ventas liquidadas y
los decreases son MCH-silenciosos, asi que check_can_revert daba falsos
permisos y el valor se fugaba sin P&L.
"""
from decimal import Decimal

TWO_PLACES = Decimal("0.01")


def incorporate_into_pool(
    liquidated: Decimal,
    avg_cost: Decimal,
    quantity: Decimal,
    unit_cost: Decimal,
) -> tuple[Decimal, Decimal]:
    """Incorpora `quantity` unidades a `unit_cost` a un pool de `liquidated`
    unidades a `avg_cost`. Retorna `(new_avg_cost, cost_adjustment)`.

    cost_adjustment: diferencia entre lo ya cargado a COGS por el hueco
    (a `avg_cost`) y el costo real de reposicion (`unit_cost`) para las
    unidades rellenadas. > 0 = se cargo COGS de mas (ganancia);
    < 0 = de menos (perdida). Siempre 0 si `liquidated >= 0`.

    Conservacion de valor por construccion:
    valor_pool_antes + quantity*unit_cost == valor_pool_despues + adjustment_implicito
    (ver tests unitarios con el encadenado del Ejemplo B del plan).
    """
    if liquidated >= 0:
        if liquidated == 0:
            return unit_cost, Decimal("0")
        new_avg = (liquidated * avg_cost + quantity * unit_cost) / (liquidated + quantity)
        return new_avg, Decimal("0")

    # Oversell: hueco de -liquidated unidades ya cargadas a COGS @ avg_cost.
    hole = -liquidated
    filled = min(hole, quantity)
    adjustment = (filled * (avg_cost - unit_cost)).quantize(TWO_PLACES)
    remaining = quantity - filled
    if remaining > 0:
        # Hueco cubierto: el resto entra limpio al costo real de reposicion.
        return unit_cost, adjustment
    # Hueco NO cubierto: lo que queda del hueco sigue "cargado" al avg previo.
    return avg_cost, adjustment


def remove_from_pool(
    liquidated: Decimal,
    avg_cost: Decimal,
    quantity: Decimal,
    unit_cost: Decimal,
) -> tuple[Decimal, Decimal]:
    """Saca del pool `quantity` unidades que habian entrado a `unit_cost`
    (remocion ponderada — reversion de una entrada). Retorna
    `(new_avg_cost, cost_adjustment)`.

    `unit_cost` debe ser la contribucion REAL de la operacion revertida:
    costo ajustado por comision + cost_adjustment de relleno prorrateado
    (H1 del plan) — no el precio crudo.

    Ecuacion de conservacion (exacta en las 3 ramas):
    pool_despues == pool_antes - quantity*unit_cost + adjustment

    Ramas:
    1. Remocion limpia (queda stock y valor >= 0): ponderado inverso, adj 0.
       Sin actividad entre la operacion y su reversion equivale al rewind.
    2. Valor insuficiente (queda stock pero el valor a remover excede el del
       pool): el avg QUEDA (evita stock a costo $0 y avg negativo) y la
       diferencia va al P&L.
    3. La remocion cruza a hueco (o lo profundiza): el hueco carga el avg
       vigente (misma semantica que incorporate) y la diferencia va al P&L.

    > 0 = el pool retiene mas valor del que la operacion se lleva (ganancia);
    < 0 = perdida. Timing: el caller lo persiste y entra al P&L por
    cancelled_at/annulled_at (G3: puede caer en periodo distinto al original).
    """
    remaining = liquidated - quantity
    if remaining > 0:
        new_value = liquidated * avg_cost - quantity * unit_cost
        if new_value >= 0:
            return new_value / remaining, Decimal("0")
        # Rama 2: el pool no contiene el valor que la operacion decia haber
        # metido (extracciones intermedias se llevaron parte a costo mezclado).
        adjustment = (quantity * (unit_cost - avg_cost)).quantize(TWO_PLACES)
        return avg_cost, adjustment
    # Rama 3: remocion vacia el pool o lo deja en hueco.
    adjustment = (quantity * (unit_cost - avg_cost)).quantize(TWO_PLACES)
    return avg_cost, adjustment
