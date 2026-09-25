"""Advisory locks de numeracion: UNA llave, UN generador, UN orden.

Cada documento numerado (compra, venta, cruce, movimiento, ajuste,
transformacion, traslado, entrada, salida de plomo) toma su consecutivo con
`SELECT MAX(numero)+1` protegido por `pg_advisory_xact_lock(llave)`. Este
modulo es el unico lugar donde se deriva la llave, se toma el lock y se lee el
MAX — los servicios solo dicen QUE contador quieren.

Por que existe (plan `plan-advisory-locks-estables.md`):

  A. La llave se derivaba con `hash()` de Python, que se aleatoriza POR PROCESO
     (PYTHONHASHSEED). Produccion corre `uvicorn --workers 4`: cuatro semillas,
     cuatro llaves distintas para la misma organizacion, y dos registros
     simultaneos en workers distintos no se serializaban. `zlib.crc32` es
     determinista y cabe en el bigint del lock.
  B. `purchase_number` y `sale_number` tenian DOS generadores cada uno (el del
     modulo y la copia de doble partida) con llaves DISTINTAS: una compra
     directa y la compra interna de un cruce nunca se serializaron entre si, ni
     con un solo worker. Con un generador por contador (`next_number`) eso es
     imposible por construccion.
  C. Con la llave por fin efectiva entre workers, dos flujos que toman los
     mismos locks en orden cruzado pasan de "no contienden" a "se esperan en
     cruz" (PG aborta uno: 40P01 → 500). Por eso hay un ORDEN CANONICO (`RANK`)
     y se EXIGE (`LockOrderError`), no se documenta: la suite revienta antes
     que produccion. Los flujos que necesitan varios locks los declaran al
     entrar con `lock_sequences(...)`, y el resto de sus adquisiciones son
     re-entrantes.

El nombre de la secuencia es el CONTADOR, no el modulo que lo pide: compras y
cruces piden `purchase_number` por igual. Un nombre fuera de `SEQUENCES` es
error (fail-closed): se registra, no se inventa.
"""
from __future__ import annotations

import zlib
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.orm import Session

# nombre de secuencia -> (tabla, columna, columna de particion | None)
SEQUENCES: dict[str, tuple[str, str, str | None]] = {
    "double_entry_number": ("double_entries", "double_entry_number", None),
    "inbound_order_number": ("inbound_orders", "order_number", None),
    "transfer_number": ("transfers", "transfer_number", None),
    "willard_delivery": ("willard_deliveries", "delivery_number", "series"),
    "crucible_number": ("crucible_charges", "charge_number", None),
    "purchase_number": ("purchases", "purchase_number", None),
    "sale_number": ("sales", "sale_number", None),
    "movement_number": ("money_movements", "movement_number", None),
    "adjustment_number": ("inventory_adjustments", "adjustment_number", None),
    "transformation_number": ("material_transformations", "transformation_number", None),
}

# Orden canonico de adquisicion dentro de UNA transaccion (D4): documento ->
# compra -> venta -> movimiento -> ajuste. Un flujo puede tomar un lock de rango
# MAYOR al que ya retiene; nunca uno menor (salvo re-adquirir el mismo).
RANK: dict[str, int] = {
    "double_entry_number": 10,
    "inbound_order_number": 11,
    "transfer_number": 12,
    "willard_delivery": 13,
    # 14 y no 13 (F2 de QA, #107): un empate de rango deja ciego a D4b — el sort
    # estable de lock_sequences y la comparacion `<` no verian dos flujos que
    # tomaran (willard, crucible) en orden cruzado.
    "crucible_number": 14,
    "purchase_number": 20,
    "sale_number": 21,
    "movement_number": 30,
    "adjustment_number": 40,
    "transformation_number": 41,
}

assert set(RANK) == set(SEQUENCES), "toda secuencia tiene rango y viceversa"
assert len(set(RANK.values())) == len(RANK), "dos secuencias con el mismo rango (F2 #107)"

_HELD_KEY = "advisory_locks_held"


class LockOrderError(RuntimeError):
    """Un flujo pidio un lock de rango menor al que ya retiene (D4b).

    No es un error de datos: es un camino de codigo que, concurrente con otro
    que adquiera en el orden canonico, podria esperarse en cruz. Se arregla
    declarando los locks al entrar al flujo con `lock_sequences(...)`.
    """


def _check_sequence(sequence: str) -> tuple[str, str, str | None]:
    try:
        return SEQUENCES[sequence]
    except KeyError:
        raise ValueError(
            f"Secuencia desconocida '{sequence}'. Las conocidas son: "
            f"{', '.join(sorted(SEQUENCES))}. Un contador nuevo se registra en "
            "app/utils/advisory_locks.py, no se inventa un nombre."
        ) from None


def sequence_lock_key(organization_id: UUID, sequence: str, partition: str | None = None) -> int:
    """Llave ESTABLE del advisory lock: crc32 de `org:secuencia[:particion]`.

    Determinista entre procesos (a diferencia de `hash()`), cabe en bigint, y
    para la serie de salidas produce exactamente la cadena que #105 estreno
    (`f"{org}:willard_delivery:{series}"`).
    """
    _check_sequence(sequence)
    key = f"{organization_id}:{sequence}"
    if partition:
        key += f":{partition}"
    return zlib.crc32(key.encode("utf-8"))


def _held(db: Session) -> set[str]:
    return db.info.setdefault(_HELD_KEY, set())


def lock_sequence(
    db: Session, organization_id: UUID, sequence: str, partition: str | None = None
) -> None:
    """Toma el advisory lock (transaccional) de un contador, exigiendo el orden canonico."""
    key = sequence_lock_key(organization_id, sequence, partition)
    held = _held(db)
    if sequence not in held:
        top = max((RANK[s] for s in held), default=-1)
        if RANK[sequence] < top:
            worst = max(held, key=RANK.__getitem__)
            raise LockOrderError(
                f"Orden de locks invalido: se pide '{sequence}' (rango {RANK[sequence]}) "
                f"con '{worst}' (rango {RANK[worst]}) ya retenido en esta transaccion. "
                "Declare los locks al entrar al flujo con lock_sequences(db, org, ...)."
            )
    db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": key})
    held.add(sequence)


def lock_sequences(db: Session, organization_id: UUID, *sequences: str) -> None:
    """Declaracion anticipada (D4): toma varios locks en orden canonico.

    Para los flujos que numeran mas de un contador en una transaccion. El orden
    lo pone el helper (rango), asi que el llamador no puede equivocarse; las
    adquisiciones posteriores de esas mismas secuencias son re-entrantes.

    ⚠️ Toma la llave SIN particion (`org:secuencia`). Para `willard_delivery`
    (particionada por serie) eso NO es la llave que usa `next_number`
    (`org:willard_delivery:serie`): hoy nadie la declara y es inerte, pero si
    un flujo llegara a numerar dos series en una transaccion, la declaracion
    necesita particion (O2 de QA, ciclo advisory-locks).
    """
    for seq in sequences:
        _check_sequence(seq)
    for seq in sorted(set(sequences), key=RANK.__getitem__):
        lock_sequence(db, organization_id, seq)


def next_number(
    db: Session, organization_id: UUID, sequence: str, partition: str | None = None
) -> int:
    """Siguiente consecutivo de un contador: lock + `COALESCE(MAX(col),0)+1`.

    El unico generador de numeros del sistema. Tabla y columna salen del mapa
    `SEQUENCES` (nunca de la entrada del usuario).
    """
    table, column, partition_col = _check_sequence(sequence)
    if partition_col and not partition:
        raise ValueError(f"La secuencia '{sequence}' se numera por '{partition_col}': falta la particion")
    if partition and not partition_col:
        raise ValueError(f"La secuencia '{sequence}' no tiene particion")
    lock_sequence(db, organization_id, sequence, partition)
    sql = f"SELECT COALESCE(MAX({column}), 0) + 1 FROM {table} WHERE organization_id = :org"
    params: dict[str, object] = {"org": str(organization_id)}
    if partition_col:
        sql += f" AND {partition_col} = :partition"
        params["partition"] = partition
    return int(db.execute(text(sql), params).scalar_one())


@event.listens_for(Session, "after_transaction_end")
def _forget_held_locks(session: Session, transaction) -> None:
    """Los advisory locks XACT mueren con la transaccion; el registro tambien.

    Solo al cerrar la transaccion RAIZ (un savepoint anidado no libera nada).
    """
    if transaction.parent is None:
        session.info.pop(_HELD_KEY, None)
