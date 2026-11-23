"""Reparto por COMPRA en la Entrada + IVA en compras (plan
docs/planes/plan-sac-reparto-por-compra.md v1.2, §7).

Johana (19-nov, via Daniel): una Entrada se liquida por proveedor, y un mismo
proveedor puede tener DOS compras en la misma Entrada — «son dos
recolecciones» (Q-65). La unidad del reparto deja de ser el proveedor y pasa a
ser la compra de la Entrada (`purchase_slot`). Y el IVA de la compra se suma y
va a la MISMA entidad `[Impuestos] IVA por Pagar` de las ventas (Daniel).

Estos tests ponen los slots A MANO; los de antes pasan por `con_slots`.
"""
import importlib.util
import pathlib
from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models.document_tax import DocumentTax
from app.models.inbound_order import InboundLineAllocation, InboundOrderLine, InboundOrderPurchase
from app.models.material import Material
from app.models.money_account import MoneyAccount
from app.models.purchase import Purchase
from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategory
from app.utils.dates import business_today
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    api_create_sale,
    create_material,
    create_material_category,
    create_warehouse,
)

INBOUND_URL = "/api/v1/inbound-orders"
PURCHASES_URL = "/api/v1/purchases"
PROFILES_URL = "/api/v1/material-kg-profiles"
STATEMENT_URL = "/api/v1/money-movements/third-party"
SIMILAR_URL = "/api/v1/third-parties/similar"
IVA_ENTITY = "[Impuestos] IVA por Pagar"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def wh(db_session, test_organization):
    w = create_warehouse(db_session, test_organization.id, "Circunvalar RC")
    db_session.commit()
    return w


def _supplier(db, org_id, name, **kw):
    tp = create_third_party_with_category(db, org_id, name, "material_supplier", **kw)
    db.commit()
    return tp


@pytest.fixture
def sup_a(db_session, test_organization):
    return _supplier(db_session, test_organization.id, "CHREPUESTOS RC")


@pytest.fixture
def sup_b(db_session, test_organization):
    return _supplier(db_session, test_organization.id, "Proveedor B RC")


@pytest.fixture
def sup_c(db_session, test_organization):
    return _supplier(db_session, test_organization.id, "Proveedor C RC")


def _mat(db, client, headers, org_id, code):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = "kg"
    db.commit()
    r = client.put(
        f"{PROFILES_URL}/{mat.id}", headers=headers,
        json={"compra_regular": True, "willard_world": "none", "lead_product": "none"},
    )
    assert r.status_code == 200, r.text
    return mat


@pytest.fixture
def m1(db_session, client, org_headers, test_organization):
    return _mat(db_session, client, org_headers, test_organization.id, "HIERRO-RC")


@pytest.fixture
def m2(db_session, client, org_headers, test_organization):
    return _mat(db_session, client, org_headers, test_organization.id, "COBRE-RC")


@pytest.fixture
def caja(db_session, test_organization):
    acc = MoneyAccount(
        name="Caja RC", account_type="cash", current_balance=Decimal("100000000"),
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


def _past(days=2):
    return (business_today() - timedelta(days=days)).isoformat()


def _entrada(client, headers, wh, lines, date=None):
    """Entrada tipo compra capturada y revisada. lines = [(material, qty)]."""
    r = client.post(INBOUND_URL, headers=headers, json={
        "inbound_type": "purchase", "warehouse_id": str(wh.id),
        "date": date or _past(),
        "lines": [{"material_id": str(m.id), "quantity": str(q), "scale_weight_kg": str(q)}
                  for m, q in lines],
    })
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    r = client.post(f"{INBOUND_URL}/{oid}/review", headers=headers)
    assert r.status_code == 200, r.text
    return oid


def _a(tp, slot, qty, price="1000", invoice=None):
    body = {"third_party_id": str(tp.id), "purchase_slot": slot,
            "quantity": str(qty), "unit_price": str(price)}
    if invoice:
        body["invoice_number"] = invoice
    return body


def _ln(mat, *allocs):
    return {"material_id": str(mat.id), "allocations": list(allocs)}


def _liq(client, headers, oid, lines, expect=200, **extra):
    r = client.post(f"{INBOUND_URL}/{oid}/liquidate", headers=headers,
                    json={"lines": lines, **extra})
    assert r.status_code == expect, r.text
    return r.json()


def _unliq(client, headers, oid):
    r = client.post(f"{INBOUND_URL}/{oid}/unliquidate", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _bridge(db, oid):
    """[(purchase_number, supplier_id, status, slot)] de la Entrada."""
    db.expire_all()
    return [
        (p.purchase_number, p.supplier_id, p.status, slot)
        for p, slot in db.execute(
            select(Purchase, InboundOrderPurchase.purchase_slot)
            .join(InboundOrderPurchase, InboundOrderPurchase.purchase_id == Purchase.id)
            .where(InboundOrderPurchase.inbound_order_id == UUID(str(oid)))
            .order_by(Purchase.purchase_number)
        ).all()
    ]


def _bal(db, tp_id) -> Decimal:
    db.expire_all()
    return Decimal(str(db.get(ThirdParty, tp_id).current_balance))


def _iva_entity(db, org_id):
    db.expire_all()
    return db.execute(select(ThirdParty).where(
        ThirdParty.organization_id == org_id, ThirdParty.name == IVA_ENTITY,
    )).scalar_one_or_none()


def _statement(client, headers, tp_id, **params):
    r = client.get(f"{STATEMENT_URL}/{tp_id}", headers=headers,
                   params={"date_from": "2026-01-01", "date_to": "2026-12-31", **params})
    assert r.status_code == 200, r.text
    return r.json()


def _corrido_cierra(client, headers, db, tp_id):
    """#55 en las DOS superficies: el saldo corrido de la ultima fila == el vivo."""
    vivo = _bal(db, tp_id)
    for view in ("events", "operations"):
        data = _statement(client, headers, tp_id, view=view)
        if not data["items"]:
            # Sin eventos (todo anulado/desliquidado) el saldo vivo es cero
            assert vivo == 0, f"{view}: sin eventos y vivo {vivo}"
            continue
        corrido = Decimal(str(data["items"][-1]["balance_after"]))
        assert corrido == vivo, f"{view}: corrido {corrido} != vivo {vivo}"
        assert Decimal(str(data["current_balance"])) == vivo


def _iva(slot, tp, amount):
    return {"purchase_slot": slot, "third_party_id": str(tp.id),
            "taxes": [{"tax_type": "iva", "rate": "19", "amount": str(amount)}]}


# ---------------------------------------------------------------------------
# T1–T6, T16–T18 — slots
# ---------------------------------------------------------------------------

class TestSlots:

    def test_t1_dos_compras_del_mismo_proveedor(
        self, client, org_headers, db_session, wh, sup_a, m1, m2,
    ):
        """Q-65: dos recolecciones del mismo proveedor en una Entrada son dos
        compras. Las cantidades son IGUALES a proposito: con el aviso de
        duplicado sin la exclusion de R8 (±20 %), saldria."""
        oid = _entrada(client, org_headers, wh, [(m1, 200), (m2, 200)])
        out = _liq(client, org_headers, oid, [
            _ln(m1, _a(sup_a, 1, 100, "1000"), _a(sup_a, 2, 100, "1100")),
            _ln(m2, _a(sup_a, 1, 100, "2000"), _a(sup_a, 2, 100, "2100")),
        ])
        rows = _bridge(db_session, oid)
        assert [(r[1], r[2], r[3]) for r in rows] == [
            (sup_a.id, "liquidated", 1), (sup_a.id, "liquidated", 2),
        ]
        totals = {r[3]: db_session.execute(select(Purchase.total_amount).where(
            Purchase.purchase_number == r[0], Purchase.supplier_id == sup_a.id,
        )).scalar_one() for r in rows}
        assert totals == {1: Decimal("300000.00"), 2: Decimal("320000.00")}
        assert _bal(db_session, sup_a.id) == Decimal("-620000")
        assert not any("mismo proveedor" in w for w in out.get("warnings", [])), out["warnings"]
        # La respuesta trae el slot de cada asignacion y de cada compra (#95)
        slots = sorted(a["purchase_slot"] for line in out["lines"] for a in line["allocations"])
        assert slots == [1, 1, 2, 2]
        assert sorted(p["purchase_slot"] for p in out["purchases"]) == [1, 2]

    def test_t2_reliquidar_sin_cambios_conserva_numeros(
        self, client, org_headers, db_session, wh, sup_a, m1, m2,
    ):
        oid = _entrada(client, org_headers, wh, [(m1, 200), (m2, 200)])
        lines = [
            _ln(m1, _a(sup_a, 1, 100, "1000"), _a(sup_a, 2, 100, "1100")),
            _ln(m2, _a(sup_a, 1, 100, "2000"), _a(sup_a, 2, 100, "2100")),
        ]
        _liq(client, org_headers, oid, lines)
        antes = [(r[0], r[3]) for r in _bridge(db_session, oid)]
        _unliq(client, org_headers, oid)
        _liq(client, org_headers, oid, lines)
        despues = _bridge(db_session, oid)
        assert [(r[0], r[3]) for r in despues] == antes
        assert all(r[2] == "liquidated" for r in despues)

    def test_t3b_intercambiar_proveedores_entre_compras(
        self, client, org_headers, db_session, wh, sup_a, sup_b, m1,
    ):
        """R6 (hueco de P2): el slot es IDENTIDAD, no el proveedor. Si se
        intercambian los proveedores de las compras 1 y 2, las dos compras
        viejas se cancelan y nacen dos nuevas — reusar «la compra de ese
        proveedor» de otro slot dejaria el puente contradiciendo el reparto
        (el 409 de T18 en la siguiente reliquidacion)."""
        oid = _entrada(client, org_headers, wh, [(m1, 200)])
        _liq(client, org_headers, oid, [_ln(m1, _a(sup_a, 1, 100), _a(sup_b, 2, 100, "1100"))])
        viejas = {r[0] for r in _bridge(db_session, oid)}
        _unliq(client, org_headers, oid)
        cruzado = [_ln(m1, _a(sup_b, 1, 100), _a(sup_a, 2, 100, "1100"))]
        _liq(client, org_headers, oid, cruzado)
        rows = _bridge(db_session, oid)
        assert all(r[2] == "cancelled" for r in rows if r[0] in viejas), rows
        vivas = [r for r in rows if r[2] != "cancelled"]
        # Puente: exactamente UNA compra viva por slot, del proveedor correcto
        assert sorted((r[3], r[1]) for r in vivas) == sorted([(1, sup_b.id), (2, sup_a.id)])
        assert all(r[2] == "liquidated" and r[0] not in viejas for r in vivas)
        # Segundo ciclo: sin 409 (puente y reparto coinciden) y mismos numeros
        numeros = sorted((r[3], r[0]) for r in vivas)
        _unliq(client, org_headers, oid)
        _liq(client, org_headers, oid, cruzado)
        despues = [r for r in _bridge(db_session, oid) if r[2] != "cancelled"]
        assert sorted((r[3], r[0]) for r in despues) == numeros
        assert all(r[2] == "liquidated" for r in despues)

    def test_t3_cambiar_el_proveedor_de_un_slot(
        self, client, org_headers, db_session, wh, sup_a, sup_b, m1,
    ):
        oid = _entrada(client, org_headers, wh, [(m1, 200)])
        _liq(client, org_headers, oid, [_ln(m1, _a(sup_a, 1, 100), _a(sup_a, 2, 100))])
        (n1, _, _, _), (n2, _, _, _) = _bridge(db_session, oid)
        _unliq(client, org_headers, oid)
        out = _liq(client, org_headers, oid, [_ln(m1, _a(sup_a, 1, 100), _a(sup_b, 2, 100))])
        rows = {r[0]: r for r in _bridge(db_session, oid)}
        assert rows[n1][2] == "liquidated" and rows[n1][1] == sup_a.id
        assert rows[n2][2] == "cancelled"
        nuevas = [r for n, r in rows.items() if n not in (n1, n2)]
        assert len(nuevas) == 1
        assert nuevas[0][1] == sup_b.id and nuevas[0][2] == "liquidated" and nuevas[0][3] == 2
        assert any(f"#{n2} salio del reparto" in w for w in out["warnings"])
        # R5: dos filas del puente con slot 2 (la cancelada y la nueva)
        assert sorted(r[3] for r in rows.values()) == [1, 2, 2]

    def test_t4_mismo_material_dos_veces_en_la_misma_compra(
        self, client, org_headers, db_session, wh, sup_a, m1,
    ):
        oid = _entrada(client, org_headers, wh, [(m1, 200)])
        out = _liq(client, org_headers, oid,
                   [_ln(m1, _a(sup_a, 1, 100), _a(sup_a, 1, 100))], expect=422)
        assert "HIERRO-RC" in out["detail"] and "compra 1" in out["detail"]
        assert _bridge(db_session, oid) == []

    def test_t5_una_compra_con_dos_proveedores(
        self, client, org_headers, db_session, wh, sup_a, sup_b, m1, m2,
    ):
        oid = _entrada(client, org_headers, wh, [(m1, 100), (m2, 100)])
        out = _liq(client, org_headers, oid,
                   [_ln(m1, _a(sup_a, 1, 100)), _ln(m2, _a(sup_b, 1, 100))], expect=422)
        assert "compra 1" in out["detail"]
        assert sup_a.name in out["detail"] and sup_b.name in out["detail"]
        assert _bridge(db_session, oid) == []

    @pytest.mark.parametrize("bloque", ["supplier_retentions", "supplier_payments", "purchase_taxes"])
    def test_t6_bloque_por_compra_con_proveedor_que_no_coincide(
        self, client, org_headers, db_session, wh, sup_a, sup_b, m1, caja, bloque,
    ):
        oid = _entrada(client, org_headers, wh, [(m1, 200)])
        block = {"purchase_slot": 1, "third_party_id": str(sup_b.id)}
        if bloque == "supplier_retentions":
            block["retentions"] = [{"retention_type": "retefuente", "amount": "100"}]
        elif bloque == "supplier_payments":
            block["account_id"] = str(caja.id)
        else:
            block["taxes"] = [{"tax_type": "iva", "amount": "100"}]
        out = _liq(client, org_headers, oid,
                   [_ln(m1, _a(sup_a, 1, 100), _a(sup_b, 2, 100))],
                   expect=422, **{bloque: [block]})
        assert "compra 1" in out["detail"] and sup_a.name in out["detail"]
        # Atomicidad leida por HTTP: la Entrada sigue revisada y sin compras
        det = client.get(f"{INBOUND_URL}/{oid}", headers=org_headers).json()
        assert det["status"] == "reviewed" and det["purchases"] == []
        assert _bal(db_session, sup_a.id) == 0 and _bal(db_session, sup_b.id) == 0

    def test_t16_slots_son_identidad(
        self, client, org_headers, db_session, test_organization, wh, sup_a, sup_b, sup_c, m1,
    ):
        """R6: quitar la compra del MEDIO no renumera: la 3 se sigue llamando 3
        y conserva su numero de compra; la 2 sale cancelada como sobrante."""
        oid = _entrada(client, org_headers, wh, [(m1, 300)])
        _liq(client, org_headers, oid,
             [_ln(m1, _a(sup_a, 1, 100), _a(sup_b, 2, 100), _a(sup_c, 3, 100))])
        by_slot = {r[3]: r[0] for r in _bridge(db_session, oid)}
        _unliq(client, org_headers, oid)
        _liq(client, org_headers, oid,
             [{**_ln(m1, _a(sup_a, 1, 150), _a(sup_c, 3, 150))}])
        rows = {r[0]: r for r in _bridge(db_session, oid)}
        assert rows[by_slot[1]][2] == "liquidated"
        assert rows[by_slot[3]][2] == "liquidated" and rows[by_slot[3]][3] == 3
        assert rows[by_slot[2]][2] == "cancelled"
        assert len(rows) == 3
        # T16+ (plan-fix-compras-de-entrada A1): este test ya pasaba por
        # update(commit=False) al cambiar 100→150 y nunca miraba el total. Los
        # montos van a mano: 150 kg × $1.000, contra los $100.000 de antes.
        db_session.expire_all()
        totales = {n: db_session.execute(select(Purchase.total_amount).where(
            Purchase.purchase_number == n,
            Purchase.organization_id == test_organization.id,
        )).scalar_one() for n in (by_slot[1], by_slot[3])}
        assert totales == {by_slot[1]: Decimal("150000"), by_slot[3]: Decimal("150000")}
        assert _bal(db_session, sup_a.id) == Decimal("-150000")
        assert _bal(db_session, sup_c.id) == Decimal("-150000")
        assert _bal(db_session, sup_b.id) == 0
        for tp in (sup_a, sup_b, sup_c):
            _corrido_cierra(client, org_headers, db_session, tp.id)

    def test_t17_aviso_de_duplicado_solo_fuera_de_la_entrada(
        self, client, org_headers, db_session, wh, sup_a, m1,
    ):
        """R8: dentro de la Entrada no avisa; otra Entrada del MISMO dia con el
        mismo proveedor y cantidad parecida SI avisa (no es una bandera que lo
        apague para todo `from_inbound`)."""
        dia = _past(3)
        o1 = _entrada(client, org_headers, wh, [(m1, 200)], date=dia)
        w1 = _liq(client, org_headers, o1, [_ln(m1, _a(sup_a, 1, 100), _a(sup_a, 2, 100))])
        assert not any("mismo proveedor" in w for w in w1["warnings"]), w1["warnings"]
        o2 = _entrada(client, org_headers, wh, [(m1, 100)], date=dia)
        w2 = _liq(client, org_headers, o2, [_ln(m1, _a(sup_a, 1, 100))])
        assert any("mismo proveedor" in w for w in w2["warnings"]), w2["warnings"]

    def test_t18_defensa_dura_puente_contradice_reparto(
        self, client, org_headers, db_session, wh, sup_a, sup_b, m1,
    ):
        """QA c: si el puente y el reparto guardado se contradicen (forzado por
        ORM: se intercambian los slots del puente), reliquidar da 409 en vez de
        reusar una compra con el proveedor cruzado."""
        oid = _entrada(client, org_headers, wh, [(m1, 200)])
        lines = [_ln(m1, _a(sup_a, 1, 100), _a(sup_b, 2, 100))]
        _liq(client, org_headers, oid, lines)
        _unliq(client, org_headers, oid)
        for link in db_session.execute(select(InboundOrderPurchase).where(
            InboundOrderPurchase.inbound_order_id == UUID(oid)
        )).scalars():
            link.purchase_slot = 3 - link.purchase_slot
        db_session.commit()
        out = _liq(client, org_headers, oid, lines, expect=409)
        assert "estado inconsistente" in out["detail"]

    def test_t18b_compra_viva_sin_slot_da_409_y_no_la_cancela(
        self, client, org_headers, db_session, wh, sup_a, sup_b, m1,
    ):
        """QA C1: una compra registrada viva en el puente SIN slot (forzado por
        ORM) no se manda a leftovers — eso la cancelaria en silencio. 409 con
        su numero, y nada escrito: sigue registrada y el puente igual."""
        oid = _entrada(client, org_headers, wh, [(m1, 200)])
        lines = [_ln(m1, _a(sup_a, 1, 100), _a(sup_b, 2, 100))]
        _liq(client, org_headers, oid, lines)
        _unliq(client, org_headers, oid)
        links = db_session.execute(select(InboundOrderPurchase).where(
            InboundOrderPurchase.inbound_order_id == UUID(oid)
        )).scalars().all()
        target = next(lk for lk in links if lk.purchase_slot == 2)
        target.purchase_slot = None
        db_session.commit()
        p = db_session.get(Purchase, target.purchase_id)
        antes = _bridge(db_session, oid)
        out = _liq(client, org_headers, oid, lines, expect=409)
        assert f"#{p.purchase_number}" in out["detail"]
        assert "sin compra asignada" in out["detail"]
        db_session.expire_all()
        assert db_session.get(Purchase, target.purchase_id).status == "registered"
        assert _bridge(db_session, oid) == antes


# ---------------------------------------------------------------------------
# T7–T10b, T15 — IVA en compras
# ---------------------------------------------------------------------------

class TestIvaCompra:

    def test_t7_liquidar_con_iva(
        self, client, org_headers, db_session, test_organization, wh, sup_a, sup_b, m1, caja,
    ):
        oid = _entrada(client, org_headers, wh, [(m1, 200)])
        caja0 = Decimal(str(caja.current_balance))
        _liq(client, org_headers, oid, [_ln(m1, _a(sup_a, 1, 100), _a(sup_b, 2, 100))],
             purchase_taxes=[_iva(1, sup_a, "19000")],
             supplier_retentions=[{"purchase_slot": 1, "third_party_id": str(sup_a.id),
                                   "retentions": [{"retention_type": "retefuente",
                                                   "amount": "2500"}]}],
             supplier_payments=[{"purchase_slot": 1, "third_party_id": str(sup_a.id),
                                 "account_id": str(caja.id)}])
        ent = _iva_entity(db_session, test_organization.id)
        assert ent is not None
        assert _bal(db_session, ent.id) == Decimal("19000")  # descuenta del IVA por pagar
        # Proveedor: −(100.000 + 19.000) + 2.500 de retencion + pago de contado
        # del NETO 100.000 + 19.000 − 2.500 = 116.500 → queda en 0
        assert _bal(db_session, sup_a.id) == 0
        db_session.expire_all()
        assert caja0 - Decimal(str(db_session.get(MoneyAccount, caja.id).current_balance)) == Decimal("116500")
        # El IVA no entra al costo: 200 kg a $1.000
        assert db_session.get(Material, m1.id).current_average_cost == Decimal("1000")
        # La compra sin IVA no tiene filas
        assert _bal(db_session, sup_b.id) == Decimal("-100000")
        tax = db_session.execute(select(DocumentTax)).scalar_one()
        assert tax.purchase_id is not None and tax.base_amount == Decimal("100000.00")

    def test_t7b_solo_iva_en_compras(
        self, client, org_headers, db_session, wh, sup_a, m1,
    ):
        """Hoy una compra solo lleva IVA: sus retenciones van por su bloque."""
        oid = _entrada(client, org_headers, wh, [(m1, 100)])
        block = {"purchase_slot": 1, "third_party_id": str(sup_a.id),
                 "taxes": [{"tax_type": "retefuente", "amount": "100"}]}
        out = _liq(client, org_headers, oid, [_ln(m1, _a(sup_a, 1, 100))],
                   expect=422, purchase_taxes=[block])
        assert "solo va el IVA" in out["detail"]
        assert _bridge(db_session, oid) == []

    def test_t8_iva_de_compra_y_de_venta_en_la_entidad(
        self, client, org_headers, db_session, test_organization, wh, sup_a, m1,
    ):
        customer = create_third_party_with_category(
            db_session, test_organization.id, "Cliente RC", "customer")
        db_session.commit()
        oid = _entrada(client, org_headers, wh, [(m1, 100)])
        _liq(client, org_headers, oid, [_ln(m1, _a(sup_a, 1, 100))],
             purchase_taxes=[_iva(1, sup_a, "19000")])
        sale = api_create_sale(
            client, org_headers, customer_id=customer.id, warehouse_id=wh.id,
            lines=[{"material_id": m1.id, "quantity": "50", "unit_price": "3000"}],
            date=_past(1),
        )
        r = client.patch(f"/api/v1/sales/{sale['id']}/liquidate", headers=org_headers, json={
            "taxes": [{"tax_type": "iva", "rate": "19", "amount": "28500"}],
        })
        assert r.status_code == 200, r.text
        ent = _iva_entity(db_session, test_organization.id)
        # Nettea: −28.500 (debe el IVA de la venta) + 19.000 (descontable)
        assert _bal(db_session, ent.id) == Decimal("-9500")
        _corrido_cierra(client, org_headers, db_session, ent.id)
        _corrido_cierra(client, org_headers, db_session, sup_a.id)
        _corrido_cierra(client, org_headers, db_session, customer.id)
        ev = _statement(client, org_headers, ent.id)["items"]
        taxes = [i for i in ev if i["event_type"] == "document_tax"]
        assert sorted((i["direction"], i["amount"]) for i in taxes) == [(-1, 28500.0), (1, 19000.0)]
        assert any("Compra #" in i["description"] for i in taxes)
        # En el estado del proveedor el IVA va DEBAJO de su compra
        tipos = [i["event_type"] for i in _statement(client, org_headers, sup_a.id)["items"]]
        assert tipos.index("purchase_liquidation") < tipos.index("document_tax"), tipos
        # Clasificacion por signo (P19): con saldo negativo la entidad es pasivo
        bd = client.get("/api/v1/reports/balance-detailed", headers=org_headers).json()
        pasivo = {i["name"] for i in bd["liabilities"]["liability_debt"]["items"]}
        assert IVA_ENTITY in pasivo

    def test_t8b_solo_iva_de_compra_es_anticipo(
        self, client, org_headers, db_session, test_organization, wh, sup_a, m1,
    ):
        """Con solo IVA descontable la entidad queda a favor: va a anticipos de
        impuestos, no al pasivo como un pasivo negativo (P19)."""
        oid = _entrada(client, org_headers, wh, [(m1, 100)])
        _liq(client, org_headers, oid, [_ln(m1, _a(sup_a, 1, 100))],
             purchase_taxes=[_iva(1, sup_a, "19000")])
        bd = client.get("/api/v1/reports/balance-detailed", headers=org_headers).json()
        activos = {i["name"] for i in bd["assets"]["tax_advances"]["items"]}
        assert IVA_ENTITY in activos

    def test_t9_desliquidar_revierte_el_iva(
        self, client, org_headers, db_session, test_organization, wh, sup_a, m1,
    ):
        """R4 por el camino de la Entrada. Al desliquidar la compra vuelve a
        `registered` sin `liquidated_at`, y sus impuestos (revertidos) salen del
        estado de cuenta con ella, igual que sus retenciones (bloque 2c). Al
        reliquidar, la fila vieja aparece con su par de reversa y la nueva viva.
        """
        oid = _entrada(client, org_headers, wh, [(m1, 100)])
        lines = [_ln(m1, _a(sup_a, 1, 100))]
        _liq(client, org_headers, oid, lines, purchase_taxes=[_iva(1, sup_a, "19000")])
        ent = _iva_entity(db_session, test_organization.id)
        _unliq(client, org_headers, oid)
        assert _bal(db_session, sup_a.id) == 0 and _bal(db_session, ent.id) == 0
        tax = db_session.execute(select(DocumentTax)).scalar_one()
        assert tax.reverted_at is not None
        # La precarga ve el ultimo lote (revertido)
        det = client.get(f"{INBOUND_URL}/{oid}", headers=org_headers).json()
        assert [t["amount"] for t in det["purchases"][0]["taxes"]] in (["19000.00"], [19000.0], ["19000"])
        _liq(client, org_headers, oid, lines, purchase_taxes=[_iva(1, sup_a, "19000")])
        assert _bal(db_session, sup_a.id) == Decimal("-119000")
        assert _bal(db_session, ent.id) == Decimal("19000")
        for tp_id in (sup_a.id, ent.id):
            _corrido_cierra(client, org_headers, db_session, tp_id)
            tipos = [i["event_type"] for i in _statement(client, org_headers, tp_id)["items"]]
            assert tipos.count("document_tax") == 2 and tipos.count("document_tax_cancellation") == 1

    def test_t9b_anular_la_entrada_revierte_el_iva(
        self, client, org_headers, db_session, test_organization, wh, sup_a, m1,
    ):
        """R4. 🔴 La premisa del plan («una compra derivada LIQUIDADA se cancela
        directo desde Compras, #82 c») NO se sostiene desde #93 D14: el guard de
        `purchase.cancel` (`purchase.py`, «anule la liquidación desde la
        Entrada») bloquea el cancel por separado en cualquier estado. El camino
        real de reversa de una compra con IVA es anular la Entrada, que delega
        en desliquidar y despues cancela con `from_inbound` — y los dos pasan
        por `_revert_liquidation_effects`, que es donde vive `revert_taxes`.
        Este test fija las dos cosas: el cancel directo sigue en 400 y la
        anulacion devuelve el IVA."""
        oid = _entrada(client, org_headers, wh, [(m1, 100)])
        _liq(client, org_headers, oid, [_ln(m1, _a(sup_a, 1, 100))],
             purchase_taxes=[_iva(1, sup_a, "19000")])
        ent = _iva_entity(db_session, test_organization.id)
        pid = db_session.execute(select(InboundOrderPurchase.purchase_id).where(
            InboundOrderPurchase.inbound_order_id == UUID(oid))).scalar_one()
        r = client.patch(f"{PURCHASES_URL}/{pid}/cancel", headers=org_headers)
        assert r.status_code == 400 and "desde la Entrada" in r.text
        assert _bal(db_session, ent.id) == Decimal("19000")

        r = client.post(f"{INBOUND_URL}/{oid}/annul", headers=org_headers,
                        json={"reason": "prueba reparto"})
        assert r.status_code == 200, r.text
        assert _bal(db_session, sup_a.id) == 0 and _bal(db_session, ent.id) == 0
        tax = db_session.execute(select(DocumentTax)).scalar_one()
        assert tax.reverted_at is not None
        db_session.expire_all()
        assert db_session.get(Purchase, pid).status == "cancelled"
        for tp_id in (sup_a.id, ent.id):
            _corrido_cierra(client, org_headers, db_session, tp_id)

    def test_t10_balance_as_of_cuenta_el_iva_en_los_dos_lados(
        self, client, org_headers, db_session, test_organization, wh, sup_a, m1,
    ):
        """R2: sin la rama Purchase en `_get_tp_balances_as_of`, el corte pierde
        el IVA del proveedor Y el de la entidad."""
        oid = _entrada(client, org_headers, wh, [(m1, 100)])
        _liq(client, org_headers, oid, [_ln(m1, _a(sup_a, 1, 100))],
             purchase_taxes=[_iva(1, sup_a, "19000")])
        ayer = (business_today() - timedelta(days=1)).isoformat()
        hoy = business_today().isoformat()

        def item(bd, name):
            found = []

            def walk(x):
                if isinstance(x, dict):
                    if x.get("name") == name and "balance" in x:
                        found.append(Decimal(str(x["balance"])))
                    for v in x.values():
                        walk(v)
                elif isinstance(x, list):
                    for v in x:
                        walk(v)
            walk(bd)
            return found

        bd_hoy = client.get("/api/v1/reports/balance-detailed", headers=org_headers,
                            params={"as_of_date": hoy}).json()
        # El detallado pinta el pasivo en valor absoluto (#19): el proveedor
        # aparece por 119.000 en la seccion de proveedores por pagar
        assert item(bd_hoy, sup_a.name) == [Decimal("119000")]
        assert item(bd_hoy, IVA_ENTITY) == [Decimal("19000")]
        bd_ayer = client.get("/api/v1/reports/balance-detailed", headers=org_headers,
                             params={"as_of_date": ayer}).json()
        assert item(bd_ayer, sup_a.name) == []
        assert item(bd_ayer, IVA_ENTITY) == []

    def test_t10b_detalle_de_la_compra_trae_el_iva(
        self, client, org_headers, db_session, wh, sup_a, sup_b, m1,
    ):
        """R9, leido por HTTP: sin esto el detalle y el PDF mostrarian el
        subtotal como el total a pagar."""
        oid = _entrada(client, org_headers, wh, [(m1, 200)])
        _liq(client, org_headers, oid, [_ln(m1, _a(sup_a, 1, 100), _a(sup_b, 2, 100))],
             purchase_taxes=[_iva(1, sup_a, "19000")])
        by_supplier = {r[1]: r for r in _bridge(db_session, oid)}
        pids = {s: db_session.execute(select(Purchase.id).where(
            Purchase.purchase_number == by_supplier[s][0])).scalar_one() for s in by_supplier}
        con = client.get(f"{PURCHASES_URL}/{pids[sup_a.id]}", headers=org_headers).json()
        assert [(t["tax_type"], Decimal(str(t["amount"]))) for t in con["taxes"]] == [("iva", Decimal("19000"))]
        assert con["taxes"][0]["third_party_name"] == IVA_ENTITY
        assert con["total_with_taxes"] == 119000.0
        sin = client.get(f"{PURCHASES_URL}/{pids[sup_b.id]}", headers=org_headers).json()
        assert sin["taxes"] == [] and sin["total_with_taxes"] is None
        # El listado no los trae (detail-only, #112)
        lst = client.get(PURCHASES_URL, headers=org_headers).json()
        assert all(p["taxes"] == [] and p["total_with_taxes"] is None for p in lst["items"])

    def test_t15_compra_directa_sin_entrada_no_cambia(
        self, client, org_headers, db_session, wh, sup_a, m1,
    ):
        """No-regresion: la compra de siempre (Costa) no toca document_taxes."""
        r = client.post(PURCHASES_URL, headers=org_headers, json={
            "supplier_id": str(sup_a.id), "date": f"{_past()}T12:00:00",
            "lines": [{"material_id": str(m1.id), "warehouse_id": str(wh.id),
                       "quantity": "100", "unit_price": "1000"}],
            "auto_liquidate": True,
        })
        assert r.status_code == 201, r.text
        assert _bal(db_session, sup_a.id) == Decimal("-100000")
        assert db_session.execute(select(DocumentTax)).first() is None
        det = client.get(f"{PURCHASES_URL}/{r.json()['id']}", headers=org_headers).json()
        assert det["taxes"] == [] and det["total_with_taxes"] is None


# ---------------------------------------------------------------------------
# T11–T12 — crear proveedor
# ---------------------------------------------------------------------------

@pytest.fixture
def lector_headers(client, db_session, test_organization):
    """Rol custom con `third_parties.view` (control positivo del permiso, #111)."""
    return _role_headers(db_session, test_organization, "lector-terceros", ["third_parties.view"])


@pytest.fixture
def sin_permiso_headers(client, db_session, test_organization):
    return _role_headers(db_session, test_organization, "sin-terceros", ["purchases.view"])


def _role_headers(db, org, tag, codes):
    from app.core.security import create_access_token, get_password_hash
    from app.models.permission import Permission
    from app.models.role import Role, RolePermission
    from app.models.user import OrganizationMember, User

    user = User(email=f"{tag}@example.com", hashed_password=get_password_hash("pass1234"),
                full_name=tag, is_active=True)
    db.add(user)
    db.flush()
    role = Role(organization_id=org.id, name=f"{tag}_rc", display_name=tag, is_system_role=False)
    db.add(role)
    db.flush()
    perms = db.execute(select(Permission).where(Permission.code.in_(codes))).scalars().all()
    assert len(perms) == len(codes)
    for p in perms:
        db.add(RolePermission(role_id=role.id, permission_id=p.id))
    db.add(OrganizationMember(user_id=user.id, organization_id=org.id, role_id=role.id))
    db.commit()
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}",
            "X-Organization-ID": str(org.id)}


class TestProveedorSimilar:

    def test_t11_match_por_nombre_e_identificacion(
        self, client, org_headers, db_session, test_organization,
    ):
        org = test_organization.id
        _supplier(db_session, org, "Chatarrería Muñoz", identification_number="900.123.456-7")
        create_third_party_with_category(db_session, org, "Cliente Lopez", "customer")
        _supplier(db_session, org, "Inactivo SA", is_active=False)
        db_session.commit()

        r = client.get(SIMILAR_URL, headers=org_headers, params={"name": "  CHATARRERIA munoz "})
        assert r.status_code == 200, r.text
        assert [x["name"] for x in r.json()] == ["Chatarrería Muñoz"]
        assert r.json()[0]["is_material_supplier"] is True

        r = client.get(SIMILAR_URL, headers=org_headers, params={"identification": "9001234567"})
        assert [x["name"] for x in r.json()] == ["Chatarrería Muñoz"]

        r = client.get(SIMILAR_URL, headers=org_headers, params={"name": "cliente lopez"})
        assert r.json()[0]["is_material_supplier"] is False
        assert len(r.json()[0]["category_ids"]) == 1

        assert client.get(SIMILAR_URL, headers=org_headers,
                          params={"name": "inactivo sa"}).json() == []
        assert client.get(SIMILAR_URL, headers=org_headers, params={"name": ""}).json() == []

    def test_t11b_no_ve_otra_organizacion(
        self, client, org_headers, db_session, test_organization, test_organization2,
    ):
        _supplier(db_session, test_organization2.id, "Ajeno RC")
        assert client.get(SIMILAR_URL, headers=org_headers,
                          params={"name": "ajeno rc"}).json() == []

    def test_t11c_sin_flag_403(self, client, org_headers, db_session, test_organization):
        test_organization.settings = {}
        db_session.commit()
        assert client.get(SIMILAR_URL, headers=org_headers,
                          params={"name": "x"}).status_code == 403

    def test_t11d_permiso(self, client, lector_headers, sin_permiso_headers):
        assert client.get(SIMILAR_URL, headers=lector_headers,
                          params={"name": "x"}).status_code == 200
        assert client.get(SIMILAR_URL, headers=sin_permiso_headers,
                          params={"name": "x"}).status_code == 403

    def test_t12_agregar_categoria_de_proveedor_conserva_la_de_cliente(
        self, client, org_headers, db_session, test_organization,
    ):
        """El PATCH reemplaza TODAS las categorias (`_sync_category_assignments`
        borra y recrea): la pantalla manda las actuales MAS la de proveedor."""
        org = test_organization.id
        cli = create_third_party_with_category(db_session, org, "Cliente Dual", "customer")
        db_session.commit()
        sim = client.get(SIMILAR_URL, headers=org_headers, params={"name": "cliente dual"}).json()[0]
        sup_cat = db_session.execute(select(ThirdPartyCategory.id).where(
            ThirdPartyCategory.organization_id == org,
            ThirdPartyCategory.behavior_type == "material_supplier",
        )).scalars().first()
        if sup_cat is None:
            _supplier(db_session, org, "Semilla Categoria")
            sup_cat = db_session.execute(select(ThirdPartyCategory.id).where(
                ThirdPartyCategory.organization_id == org,
                ThirdPartyCategory.behavior_type == "material_supplier",
            )).scalars().first()
        r = client.patch(f"/api/v1/third-parties/{cli.id}", headers=org_headers,
                         json={"category_ids": [*sim["category_ids"], str(sup_cat)]})
        assert r.status_code == 200, r.text
        after = client.get(SIMILAR_URL, headers=org_headers, params={"name": "cliente dual"}).json()[0]
        assert after["is_material_supplier"] is True
        assert len(after["category_ids"]) == 2


# ---------------------------------------------------------------------------
# T13–T14 — migracion: gate y backfill
# ---------------------------------------------------------------------------

def _migration():
    path = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions" / "d6e8f0a2b4c7_reparto_por_compra.py"
    spec = importlib.util.spec_from_file_location("mig_reparto_por_compra", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMigracion:

    def test_t13_gate_dos_compras_vivas_del_mismo_proveedor(
        self, client, org_headers, db_session, wh, sup_a, m1,
    ):
        """Antes de este ciclo era imposible; si aparece, la migracion se
        detiene con el listado en vez de inventar slots."""
        oid = _entrada(client, org_headers, wh, [(m1, 200)])
        _liq(client, org_headers, oid, [_ln(m1, _a(sup_a, 1, 100), _a(sup_a, 2, 100))])
        with pytest.raises(RuntimeError, match="dos compras VIVAS"):
            _migration().backfill_slots(db_session.connection())
        db_session.rollback()

    def test_t14_backfill_determinista_y_reliquida_igual(
        self, client, org_headers, db_session, wh, sup_a, sup_b, m1,
    ):
        """R7: el backfill es UNA funcion para asignaciones y puente, sale
        igual en los dos lados, y una Entrada desliquidada y una legacy 1:1
        reliquidan con los mismos numeros."""
        oid = _entrada(client, org_headers, wh, [(m1, 200)])
        lines = [_ln(m1, _a(sup_a, 1, 100), _a(sup_b, 2, 100))]
        _liq(client, org_headers, oid, lines)
        _unliq(client, org_headers, oid)
        antes = [(r[0], r[1], r[3]) for r in _bridge(db_session, oid)]

        legacy = _entrada(client, org_headers, wh, [(m1, 50)])
        _liq(client, org_headers, legacy, [_ln(m1, _a(sup_b, 1, 50))])
        _unliq(client, org_headers, legacy)

        # Estado "pre-migracion" simulado: slots revueltos en las asignaciones
        # y el puente en NULL; la legacy sin asignaciones (pre-#93)
        db_session.expire_all()
        for alloc in db_session.execute(select(InboundLineAllocation)).scalars():
            alloc.purchase_slot += 10
        for link in db_session.execute(select(InboundOrderPurchase)).scalars():
            link.purchase_slot = None
        legacy_line_ids = db_session.execute(select(InboundOrderLine.id).where(
            InboundOrderLine.inbound_order_id == UUID(legacy))).scalars().all()
        for alloc in db_session.execute(select(InboundLineAllocation).where(
            InboundLineAllocation.inbound_line_id.in_(legacy_line_ids))).scalars():
            db_session.delete(alloc)
        db_session.commit()

        slot_of_supplier, slot_of_purchase = _migration().backfill_slots(db_session.connection())
        db_session.commit()
        assert [(r[0], r[1], r[3]) for r in _bridge(db_session, oid)] == antes
        # Los dos lados salen de la misma funcion y coinciden
        for (order_id, supplier_id), slot in slot_of_supplier.items():
            if str(order_id) != oid:
                continue
            purch = [s for (o, pid), s in slot_of_purchase.items()
                     if o == order_id and db_session.get(Purchase, pid).supplier_id == supplier_id]
            assert purch == [slot]
        assert [r[3] for r in _bridge(db_session, legacy)] == [1]

        _liq(client, org_headers, oid, lines)
        assert [(r[0], r[1], r[3]) for r in _bridge(db_session, oid)] == antes
        n_legacy = _bridge(db_session, legacy)[0][0]
        _liq(client, org_headers, legacy, [_ln(m1, _a(sup_b, 1, 50))])
        assert [(r[0], r[2]) for r in _bridge(db_session, legacy)] == [(n_legacy, "liquidated")]

    def test_t14b_compute_slots_reglas(self):
        """Regla exacta (R7): primero los que tienen compra viva, por su numero
        mas bajo; despues los demas por nombre normalizado y luego id. Una
        cancelada sin slot de proveedor toma el siguiente libre."""
        mig = _migration()
        o = "orden"
        a, b, c, d = "id-a", "id-b", "id-c", "id-d"
        names = {a: "Zeta", b: "álamo", c: "Beta", d: "Delta"}
        slot_sup, slot_pur = mig.compute_slots(
            [(o, a), (o, b), (o, c)],
            [(o, "p7", a, 7, "liquidated"), (o, "p3", c, 3, "registered"),
             (o, "p9", d, 9, "cancelled")],
            names,
        )
        assert slot_sup == {(o, c): 1, (o, a): 2, (o, b): 3}
        assert slot_pur == {(o, "p3"): 1, (o, "p7"): 2, (o, "p9"): 4}
        assert mig.live_duplicates([(o, "p1", a, 1, "liquidated"), (o, "p2", a, 2, "cancelled")]) == []
