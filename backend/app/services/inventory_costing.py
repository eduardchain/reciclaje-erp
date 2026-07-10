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

Callers actuales: liquidacion de compra (purchase.py, con el costo AJUSTADO
por comision — G1) y cancelacion de venta liquidada (sale.py, reingreso
ponderado al COGS historico). Ajustes/transformaciones adoptaran el helper
en una fase posterior (plan seccion 4.3).
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
