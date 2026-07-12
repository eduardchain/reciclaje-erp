"""
Motor de calculo de intereses de obligaciones financieras (plan F).

Interes SIMPLE mensual sobre capital vigente, prorrateado por dias con base 30
SIEMPRE (30/360). Mes contable del 1 al 30: el dia 31 se trata como dia 30 y
en febrero los dias 29/30 "virtuales" corren con el ultimo saldo del mes.
El dia del evento (abono/desembolso) cuenta con el saldo NUEVO desde ese dia
inclusive.

Funciones puras sin DB — el service deriva los eventos de capital desde los
MoneyMovements confirmados y delega aca la matematica (unit-testeable).

Ejemplo canonico del cliente: deben $20M al 2% mensual, abonan $10M el dia 16
→ 20M × 2% × 15/30 + 10M × 2% × 15/30 = $200.000 + $100.000 = $300.000.
"""
from decimal import Decimal

DAYS_BASE = 30
TWO_PLACES = Decimal("0.01")
_ZERO = Decimal("0")


def _clamp_day(day: int) -> int:
    """Dia efectivo en base 30: dia 31 → 30; dias < 1 → 1 (saldo de apertura)."""
    return max(1, min(day, DAYS_BASE))


def _fmt_money(value: Decimal) -> str:
    """Formato colombiano: $20.000.000 (con coma decimal solo si no es entero)."""
    q = value.quantize(TWO_PLACES)
    if q == q.to_integral_value():
        return f"${int(q):,}".replace(",", ".")
    # 1,234,567.89 → 1.234.567,89
    s = f"{q:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"${s}"


def build_capital_events(
    opening_capital: Decimal,
    day_deltas: list[tuple[int, Decimal]],
) -> list[tuple[int, Decimal]]:
    """Convierte deltas de capital por dia en eventos de saldo vigente.

    day_deltas: [(dia, ±monto)] — positivo sube el capital (desembolso),
    negativo lo baja (abono/recaudo). Varios eventos el mismo dia se NETEAN
    (colapsan al ultimo saldo del dia). Retorna [(1, apertura), (dia, saldo
    vigente desde ese dia), ...] ordenado, listo para compute_monthly_interest.
    """
    deltas_by_day: dict[int, Decimal] = {}
    for day, delta in day_deltas:
        d = _clamp_day(day)
        deltas_by_day[d] = deltas_by_day.get(d, _ZERO) + delta

    running = opening_capital + deltas_by_day.pop(1, _ZERO)
    events: list[tuple[int, Decimal]] = [(1, running)]
    for day in sorted(deltas_by_day):
        running += deltas_by_day[day]
        events.append((day, running))
    return events


def compute_monthly_interest(
    capital_events: list[tuple[int, Decimal]],
    monthly_rate: Decimal,
) -> tuple[Decimal, str]:
    """Interes del mes por tramos sobre saldo vigente, base 30/360.

    capital_events: [(dia_efectivo 1..30, capital_vigente_desde_ese_dia)].
    Cada tramo corre del dia del evento (inclusive) hasta el dia anterior al
    siguiente evento; el ultimo llega al dia 30. Interes = Σ saldo_tramo ×
    (rate/100) × dias_tramo/30, quantize 0.01 sobre el TOTAL (no por tramo).

    Retorna (monto, desglose humano "$X × Nd + $Y × Md @ R%").
    """
    if not capital_events:
        return _ZERO.quantize(TWO_PLACES), "sin capital"

    # Normalizar: clamp de dia + colapsar mismo dia (gana el ultimo) + ordenar
    by_day: dict[int, Decimal] = {}
    for day, capital in capital_events:
        by_day[_clamp_day(day)] = capital
    days = sorted(by_day)
    if days[0] != 1:
        # Sin evento el dia 1 → capital $0 hasta el primer evento
        by_day[1] = _ZERO
        days.insert(0, 1)

    total = _ZERO
    parts: list[str] = []
    for i, day in enumerate(days):
        next_day = days[i + 1] if i + 1 < len(days) else DAYS_BASE + 1
        tramo_days = next_day - day
        capital = by_day[day]
        if tramo_days <= 0 or capital == 0:
            continue
        total += (
            capital
            * (monthly_rate / Decimal("100"))
            * Decimal(tramo_days)
            / Decimal(DAYS_BASE)
        )
        parts.append(f"{_fmt_money(capital)} × {tramo_days}d")

    amount = total.quantize(TWO_PLACES)
    if not parts:
        return amount, "capital $0 todo el mes"

    rate_str = format(monthly_rate.normalize(), "f")
    return amount, f"{' + '.join(parts)} @ {rate_str}%"
