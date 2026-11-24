"""Talonario de remisiones de SAC (plan-sac-documentos-control v1.2 §4.5).

Q-75 (Daniel, 24-nov): las Salidas de control usan el MISMO talonario de
remisiones que las Entradas, Willard incluidas (D11, confirmado por Daniel).
Los dos documentos solo comparten la remision, asi que lo comun es una
LECTURA, no un modelo.

UNA sola llave, en SQL (C1 de QA 2): `remission_key` arma las expresiones que
usan TODOS los consumidores — el orden de la lista de Entradas (#117), el orden
y la marca «Repetida» del talonario, y el aviso de remision repetida. No hay
normalizacion en Python: el regex de PostgreSQL '^[0-9]+$' es ASCII («١٢» y «²»
son texto), mientras que `str.isdigit()` los tomaria como numeros.

Salidas de Plomo NO esta en el talonario: su remision es el numero de Willard,
digitado a mano (#105, Q-27), no el talonario de SAC (O3 de QA 2).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Numeric, String, case, cast, func, literal, select, union_all
from sqlalchemy.orm import Session

from app.models.control_dispatch import ControlDispatch, ControlDispatchLine
from app.models.inbound_order import InboundOrder, InboundOrderLine
from app.models.material import Material


@dataclass(frozen=True)
class RemissionKey:
    """Expresiones SQL de una remision (columna o parametro ligado)."""

    r: object          # NULLIF(TRIM(col), '') — la vacia es NULL
    vacia: object      # r IS NULL
    numerica: object   # NUMERIC si r es solo digitos ASCII, si no NULL
    texto: object      # lower(r)
    llave: object      # 'n:<numero>' | 't:<lower>' | NULL si vacia


def remission_key(col) -> RemissionKey:
    """La UNICA definicion de «misma remision».

    - vacia: NULL, '' o solo espacios (la misma definicion de #117).
    - numerica: solo si r es solo digitos ASCII; el CASE impide castear texto
      (sin el, la primera remision de texto daria DataError). NUMERIC no tiene
      limite de digitos: una de 20 digitos no desborda. «0012» vale 12.
    - texto: lower() de PostgreSQL. Para ORDENAR se le agrega COLLATE "C"
      (independiente de la collation del server, #108/#117); para COMPARAR
      basta la igualdad del lower del mismo server.
    - llave: «0012», «12» y « 12 » dan 'n:12'; «R-12» y «r-12 » dan 't:r-12';
      «12.0» y «16.300» son texto y no chocan con 'n:12' ni 'n:16300'.
    """
    r = func.nullif(func.trim(col), "")
    numerica = case((r.op("~")("^[0-9]+$"), cast(r, Numeric)), else_=None)
    texto = func.lower(r)
    llave = case(
        (numerica.is_not(None), literal("n:", String) + cast(numerica, String)),
        else_=literal("t:", String) + texto,
    )
    return RemissionKey(r=r, vacia=r.is_(None), numerica=numerica, texto=texto, llave=llave)


def remission_order(col, desc: bool, tiebreak: list) -> list:
    """Orden natural de la remision (#117) sobre la llave unica.

    1. Vacia al FINAL en los dos sentidos.
    2. Numericas por valor; su posicion frente al texto va EXPLICITA:
       numericas antes que texto en asc, texto antes en desc.
    3. Texto: lower(r) COLLATE "C" (lower PRIMERO, despues el COLLATE).
    4. Desempate `tiebreak` (orden TOTAL para que la paginacion no repita).
    """
    k = remission_key(col)
    texto = k.texto.collate("C")
    if desc:
        return [k.vacia.asc(), k.numerica.desc().nulls_first(), texto.desc(), *tiebreak]
    return [k.vacia.asc(), k.numerica.asc().nulls_last(), texto.asc(), *tiebreak]


# ---------------------------------------------------------------------------
# Aviso de remision repetida (D8: se AVISA, no se rechaza)
# ---------------------------------------------------------------------------

def duplicate_remission_warning(
    db: Session,
    organization_id: UUID,
    remission: Optional[str],
    exclude_inbound_id: Optional[UUID] = None,
    exclude_dispatch_id: Optional[UUID] = None,
) -> Optional[str]:
    """Si otro documento del talonario NO anulado tiene la misma llave,
    devuelve el aviso que lo NOMBRA. La remision nueva se normaliza EN SQL
    con el mismo helper (C1): nada de Python decide la igualdad.

    Las anuladas no cuentan: anular y recapturar con la misma remision es el
    camino normal de corregir un error."""
    if remission is None:
        return None
    key_new = remission_key(literal(remission, String)).llave
    # Si la remision nueva es vacia, la llave es NULL y `= NULL` no matchea:
    # las vacias nunca son repetidas.
    io_key = remission_key(InboundOrder.remission_number).llave
    q_io = select(InboundOrder.order_number).where(
        InboundOrder.organization_id == organization_id,
        InboundOrder.status != "annulled",
        io_key == key_new,
    )
    if exclude_inbound_id is not None:
        q_io = q_io.where(InboundOrder.id != exclude_inbound_id)
    hit = db.execute(q_io.order_by(InboundOrder.order_number).limit(1)).scalar_one_or_none()
    if hit is not None:
        return f"La remision {remission.strip()} ya esta en la Entrada #{hit}"

    cd_key = remission_key(ControlDispatch.remission_number).llave
    q_cd = select(ControlDispatch.dispatch_number).where(
        ControlDispatch.organization_id == organization_id,
        ControlDispatch.status != "annulled",
        cd_key == key_new,
    )
    if exclude_dispatch_id is not None:
        q_cd = q_cd.where(ControlDispatch.id != exclude_dispatch_id)
    hit = db.execute(q_cd.order_by(ControlDispatch.dispatch_number).limit(1)).scalar_one_or_none()
    if hit is not None:
        return f"La remision {remission.strip()} ya esta en la Salida de control #{hit}"
    return None


# ---------------------------------------------------------------------------
# Vista del talonario (GET /remissions)
# ---------------------------------------------------------------------------

def _union(organization_id: UUID):
    """UNION ALL de los dos documentos del talonario, con columnas minimas.
    Entradas de los dos tipos (D11); Salidas de Plomo fuera (O3)."""
    io = select(
        literal("inbound", String).label("doc_type"),
        InboundOrder.id.label("doc_id"),
        InboundOrder.order_number.label("doc_number"),
        InboundOrder.remission_number.label("remission"),
        InboundOrder.date.label("date"),
        InboundOrder.status.label("status"),
        InboundOrder.inbound_type.label("inbound_type"),
    ).where(InboundOrder.organization_id == organization_id)
    cd = select(
        literal("control_dispatch", String).label("doc_type"),
        ControlDispatch.id.label("doc_id"),
        ControlDispatch.dispatch_number.label("doc_number"),
        ControlDispatch.remission_number.label("remission"),
        ControlDispatch.date.label("date"),
        ControlDispatch.status.label("status"),
        literal(None, String).label("inbound_type"),
    ).where(ControlDispatch.organization_id == organization_id)
    return union_all(io, cd).subquery("talonario")


def remission_book(
    db: Session,
    organization_id: UUID,
    remission_from: Optional[int] = None,
    remission_to: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    search: Optional[str] = None,
    desc: bool = True,
    skip: int = 0,
    limit: int = 100,
) -> dict:
    """Filas del talonario + huecos + conteo de Entradas sin remision.

    Huecos (C2 de QA 2): un numero es hueco SOLO si ningun documento del
    talonario de la org lo tiene, cualquiera sea su fecha o su estado (las
    anuladas cubren su numero). El filtro decide que filas se MUESTRAN; nunca
    que numeros existen. Se intercalan entre filas numericas CONSECUTIVAS de
    la lista filtrada ENTERA (no de la pagina). Con busqueda activa no hay
    huecos: el resultado de una busqueda no es un tramo del talonario.

    N1 de QA 2: con el filtro desde/hasta (numerico), las remisiones de texto
    NO salen — el filtro es un tramo de numeros."""
    t = _union(organization_id)
    k = remission_key(t.c.remission)

    base = select(
        t.c.doc_type, t.c.doc_id, t.c.doc_number, t.c.remission, t.c.date,
        t.c.status, t.c.inbound_type, k.numerica.label("num"), k.llave.label("llave"),
    ).where(k.vacia.is_(False))

    # «Repetida»: llaves con mas de un documento NO anulado, sobre TODA la org
    # (antes de filtrar). Las vacias no tienen llave y ya quedaron fuera.
    dup_keys = {
        llave for (llave,) in db.execute(
            select(k.llave).select_from(t)
            .where(k.vacia.is_(False), t.c.status != "annulled")
            .group_by(k.llave)
            .having(func.count() > 1)
        ).all()
    }

    filtered = base
    if remission_from is not None:
        filtered = filtered.where(k.numerica >= remission_from)
    if remission_to is not None:
        filtered = filtered.where(k.numerica <= remission_to)
    if date_from is not None:
        filtered = filtered.where(t.c.date >= date_from)
    if date_to is not None:
        filtered = filtered.where(t.c.date <= date_to)
    searching = bool(search and search.strip())
    if searching:
        filtered = filtered.where(t.c.remission.ilike(f"%{search.strip()}%"))

    # O1 de QA 2: en la VISTA las remisiones de texto van al FINAL en los dos
    # sentidos (plan §4.5): Johana abre el talonario y arriba ve la serie, no
    # una remision de texto. `remission_order` es el orden de Entradas (#117,
    # texto arriba en desc) y NO se toca: estas llaves son solo del talonario.
    # (La vacia no llega aca: `base` la excluye.)
    texto = k.texto.collate("C")
    tiebreak = [t.c.date.desc(), t.c.doc_number.desc()]
    if desc:
        order = [k.numerica.is_(None).asc(), k.numerica.desc(), texto.desc(), *tiebreak]
    else:
        order = [k.numerica.is_(None).asc(), k.numerica.asc(), texto.asc(), *tiebreak]
    rows = db.execute(filtered.order_by(*order)).all()
    total = len(rows)

    # Conjunto de numeros de TODA la org (todas las fechas, todos los estados)
    all_nums = sorted(
        int(n) for (n,) in db.execute(
            select(k.numerica).select_from(t).where(k.numerica.is_not(None)).distinct()
        ).all()
    )

    items: list[dict] = []
    prev_num: Optional[int] = None
    for row in rows:
        num = int(row.num) if row.num is not None else None
        if not searching and prev_num is not None and num is not None:
            lo, hi = sorted((prev_num, num))
            ranges = _missing_ranges(all_nums, lo, hi)
            if prev_num > num:  # orden descendente: los tramos tambien
                ranges.reverse()
            for a, b in ranges:
                # Como TEXTO: una remision de 20 digitos pasa 2^53 y JavaScript
                # la pintaria redondeada. Python la calcula exacta; el JSON la
                # entrega exacta.
                items.append({"kind": "gap", "gap_from": str(a), "gap_to": str(b),
                              "count": str(b - a + 1)})
        items.append({
            "kind": "doc",
            "doc_type": row.doc_type,
            "doc_id": row.doc_id,
            "doc_number": row.doc_number,
            "remission": row.remission,
            "date": row.date,
            "status": row.status,
            "inbound_type": row.inbound_type,
            "duplicated": row.status != "annulled" and row.llave in dup_keys,
        })
        if num is not None:
            prev_num = num

    # Paginacion DESPUES de intercalar: los huecos se calcularon sobre la
    # lista filtrada entera (T22). Un hueco viaja con la fila que lo sigue.
    page = items[skip: skip + limit]
    _attach_materials(db, organization_id, page)

    no_remission_q = select(func.count(InboundOrder.id)).where(
        InboundOrder.organization_id == organization_id,
        remission_key(InboundOrder.remission_number).vacia,
    )
    if date_from is not None:
        no_remission_q = no_remission_q.where(InboundOrder.date >= date_from)
    if date_to is not None:
        no_remission_q = no_remission_q.where(InboundOrder.date <= date_to)

    return {
        "items": page,
        "total": len(items),
        "documents": total,
        "inbound_without_remission": db.execute(no_remission_q).scalar_one(),
    }


def _missing_ranges(all_nums: list[int], lo: int, hi: int) -> list[tuple[int, int]]:
    """Tramos de numeros ESTRICTAMENTE entre lo y hi que ningun documento de
    la org tiene. `all_nums` esta ordenado; recorrido lineal acotado al tramo."""
    import bisect

    out: list[tuple[int, int]] = []
    i = bisect.bisect_right(all_nums, lo)
    cursor = lo + 1
    while i < len(all_nums) and all_nums[i] < hi:
        n = all_nums[i]
        if n > cursor:
            out.append((cursor, n - 1))
        cursor = max(cursor, n + 1)
        i += 1
    if cursor <= hi - 1:
        out.append((cursor, hi - 1))
    return out


def _attach_materials(db: Session, organization_id: UUID, items: list[dict]) -> None:
    """Materiales en una linea, SOLO para las filas de la pagina (lookup por
    pagina, nunca un join 1:N — #89/#93 R2)."""
    io_ids = [i["doc_id"] for i in items if i["kind"] == "doc" and i["doc_type"] == "inbound"]
    cd_ids = [i["doc_id"] for i in items if i["kind"] == "doc" and i["doc_type"] == "control_dispatch"]
    by_doc: dict = {}
    if io_ids:
        for doc_id, code in db.execute(
            select(InboundOrderLine.inbound_order_id, Material.code)
            .join(Material, Material.id == InboundOrderLine.material_id)
            .where(InboundOrderLine.inbound_order_id.in_(io_ids))
            .order_by(Material.code)
        ).all():
            by_doc.setdefault(("inbound", doc_id), []).append(code)
    if cd_ids:
        for doc_id, code in db.execute(
            select(ControlDispatchLine.dispatch_id, Material.code)
            .join(Material, Material.id == ControlDispatchLine.material_id)
            .where(ControlDispatchLine.dispatch_id.in_(cd_ids))
            .order_by(Material.code)
        ).all():
            by_doc.setdefault(("control_dispatch", doc_id), []).append(code)
    for i in items:
        if i["kind"] == "doc":
            i["materials"] = ", ".join(by_doc.get((i["doc_type"], i["doc_id"]), []))
