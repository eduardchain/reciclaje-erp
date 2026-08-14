"""Orden del estado de cuenta: un solo reloj por posicion de la llave.

La llave es (dia de negocio, clase de evento, instante real, numero, emision).
Cada posicion compara UNA sola cosa — la doctrina de #91 aplicada al orden.

Lo que se rompia antes (2026-08-13):

  Los eventos comerciales pasaban `liquidated_at` como desempate. Ese campo
  PARECE timestamp y es una fecha de negocio (mediodia UTC, la trampa de #87),
  asi que:

  (a) todas las operaciones del mismo dia empataban EXACTO y el orden lo decidia
      lo que Postgres devolviera sin ORDER BY. En dev salia la compra #7 antes
      que la #4.
  (b) mezclar ese mediodia-UTC con `created_at` real hacia que un movimiento de
      tesoreria del dia cayera antes o despues de las operaciones segun si se
      digito antes o despues de las 7:00 a.m. de Bogota — y anulaba a `sort_key`,
      que quedaba despues en la llave y nunca alcanzaba a decidir nada.

`test_treasury_lands_after_operations_...` y `test_operation_and_commission_...`
fallan contra el codigo viejo. El tercero fija la promesa que reporto Daniel.
"""
import pytest
from datetime import timedelta
from sqlalchemy import text

from app.utils.dates import business_today
from tests.conftest import create_third_party_with_category, _get_or_create_category
from tests.integration_helpers import (
    create_material_category, create_business_unit, create_material,
    create_warehouse, create_account, api_money_movement,
)
from app.models.third_party_category import ThirdPartyCategoryAssignment


@pytest.fixture
def esc(db_session, test_organization):
    org_id = test_organization.id
    cat = create_material_category(db_session, org_id, "Metales ORD")
    bu = create_business_unit(db_session, org_id, "UN ORD")
    material = create_material(db_session, org_id, "ORD-FE", "Chatarra ORD", cat.id, bu.id)
    warehouse = create_warehouse(db_session, org_id, "Bodega ORD")
    account = create_account(db_session, org_id, "Cuenta ORD", balance=50_000_000)
    supplier = create_third_party_with_category(
        db_session, org_id, "Proveedor ORD", "material_supplier")

    # Tercero con DOS roles: proveedor de la compra Y comisionista de esa misma
    # compra. Es lo que hace visible la adyacencia en UN solo estado de cuenta.
    dual = create_third_party_with_category(
        db_session, org_id, "Proveedor-Comisionista ORD", "material_supplier")
    db_session.add(ThirdPartyCategoryAssignment(
        third_party_id=dual.id,
        category_id=_get_or_create_category(db_session, org_id, "service_provider").id,
    ))
    db_session.commit()
    return {"material": material, "warehouse": warehouse, "account": account,
            "supplier": supplier, "dual": dual}


def _compra(client, headers, *, supplier_id, material_id, warehouse_id, dia,
            auto_liquidate=False, commissions=None):
    """POST directo: el helper compartido no expone `commissions`."""
    payload = {
        "supplier_id": str(supplier_id),
        "date": f"{dia.isoformat()}T12:00:00",
        "lines": [{"material_id": str(material_id), "quantity": 10,
                   "unit_price": 100, "warehouse_id": str(warehouse_id)}],
        "auto_liquidate": auto_liquidate,
    }
    if commissions:
        payload["commissions"] = commissions
    r = client.post("/api/v1/purchases", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _liquidar(client, headers, purchase_id, dia):
    r = client.patch(f"/api/v1/purchases/{purchase_id}/liquidate",
                     json={"liquidation_date": f"{dia.isoformat()}T12:00:00"},
                     headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _statement(client, headers, tp_id, date_from):
    r = client.get(
        f"/api/v1/money-movements/third-party/{tp_id}",
        params={"date_from": date_from.isoformat(), "limit": 500},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["items"]


class TestStatementOrdering:

    def test_same_day_operations_ordered_by_document(
        self, client, org_headers, esc,
    ):
        """Tres compras liquidadas el mismo dia salen #1, #2, #3.

        El sintoma que reporto Daniel: en dev salia #7 antes que #4. Se liquidan
        en orden INVERSO a proposito — el UPDATE reescribe la fila y la mueve de
        lugar en el heap, que es exactamente como se ensucio el orden en dev.
        """
        dia = business_today() - timedelta(days=3)
        ids = [
            _compra(client, org_headers, supplier_id=esc["supplier"].id,
                    material_id=esc["material"].id,
                    warehouse_id=esc["warehouse"].id, dia=dia)["id"]
            for _ in range(3)
        ]
        for pid in reversed(ids):
            _liquidar(client, org_headers, pid, dia)

        items = _statement(client, org_headers, esc["supplier"].id, dia)
        numeros = [i["source_number"] for i in items
                   if i["event_type"] == "purchase_liquidation"]
        assert numeros == sorted(numeros), (
            f"Las compras del mismo dia no salen en orden de documento: {numeros}"
        )

    def test_treasury_lands_after_operations_regardless_of_the_hour(
        self, client, org_headers, db_session, esc,
    ):
        """El pago digitado a las 6 a.m. ya no se cuela antes de la compra.

        🔴 Falla contra el codigo viejo: con `created_at` = 11:00 UTC (06:00 en
        Bogota) el movimiento quedaba ANTES del mediodia-UTC de la compra. El
        pivote invisible eran las 7:00 a.m., el mismo artefacto de #87.
        """
        dia = business_today() - timedelta(days=3)
        p = _compra(client, org_headers, supplier_id=esc["supplier"].id,
                    material_id=esc["material"].id,
                    warehouse_id=esc["warehouse"].id, dia=dia, auto_liquidate=True)
        mm = api_money_movement(client, org_headers, "supplier-payment", {
            "supplier_id": str(esc["supplier"].id), "amount": 500,
            "account_id": str(esc["account"].id), "date": f"{dia.isoformat()}T12:00:00",
            "description": "Abono de las 6 a.m.",
        })

        # 06:00 Bogota = 11:00 UTC, antes del mediodia-UTC de la fecha de negocio
        db_session.execute(
            text("UPDATE money_movements SET created_at = :ts WHERE id = :id"),
            {"ts": f"{dia.isoformat()} 11:00:00+00", "id": mm["id"]},
        )
        db_session.commit()

        items = _statement(client, org_headers, esc["supplier"].id, dia)
        tipos = [i["event_type"] for i in items]
        assert tipos.index("purchase_liquidation") < tipos.index("payment_to_supplier"), (
            f"El movimiento de tesoreria se colo antes de la operacion: {tipos}"
        )
        assert p["status"] == "liquidated"

    def test_operation_and_commission_stay_adjacent(
        self, client, org_headers, esc,
    ):
        """Cada compra sale pegada a su comision, no todas las compras y luego
        todas las comisiones.

        🔴 Falla contra el codigo viejo: con todo empatado, el orden lo daba la
        emision — el loop de compras corre entero antes que el de comisiones, asi
        que salia [C1, C2, Com1, Com2].
        """
        dia = business_today() - timedelta(days=3)
        tp = esc["dual"]
        for _ in range(2):
            _compra(client, org_headers, supplier_id=tp.id,
                    material_id=esc["material"].id,
                    warehouse_id=esc["warehouse"].id, dia=dia, auto_liquidate=True,
                    commissions=[{"third_party_id": str(tp.id),
                                  "concept": "Intermediacion",
                                  "commission_type": "fixed",
                                  "commission_value": 30}])

        items = _statement(client, org_headers, tp.id, dia)
        secuencia = [(i["event_type"], i["source_number"]) for i in items
                     if i["event_type"] in ("purchase_liquidation", "purchase_commission")]
        assert secuencia == [
            ("purchase_liquidation", 1), ("purchase_commission", 1),
            ("purchase_liquidation", 2), ("purchase_commission", 2),
        ], f"La comision se despego de su compra: {secuencia}"
