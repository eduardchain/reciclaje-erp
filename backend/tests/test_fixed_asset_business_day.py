"""Un solo reloj por evento — baja y venta de activos fijos.

Detonante: `sell()` fechaba el `MoneyMovement` con el dia colombiano
(`ZoneInfo("America/Bogota")` -> mediodia UTC) y el `disposed_at` con
`datetime.now(timezone.utc)`. Entre las 00:00 y 05:00 UTC (19:00-24:00 en
Colombia) esos dos relojes caen en DIAS DISTINTOS, y como
`_fa_existed_at_cutoff` usa `disposed_at` como frontera mientras los saldos
as-of usan `MoneyMovement.date`, el balance a la fecha de la venta mostraba la
plata adentro y el activo TODAVIA en libros: no cuadraba. Y no era solo esa
noche — `disposed_at` quedaba grabado en el dia siguiente para siempre, asi
que cualquier consulta futura de ese corte seguia mintiendo.

`dispose()` (#21, mucho mas viejo que la venta) tenia el patron identico.
`revalue()` se salvo porque #67 ya habia aprendido la leccion y anclo su
as-of al `MoneyMovement.date` — la leccion no se habia propagado.

⚠️ Los dos tests de invariante son los que valen: se sostienen a CUALQUIER
hora. Los de balance solo demuestran el sintoma cuando la suite corre dentro
de la franja; fuera de ella pasan igual antes y despues del arreglo.
"""
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.models.expense_category import ExpenseCategory
from app.models.fixed_asset import FixedAsset
from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement

BASE_URL = "/api/v1/fixed-assets"


def _business_today() -> datetime:
    """El mismo dia de negocio que debe usar el servicio."""
    col = datetime.now(ZoneInfo("America/Bogota")).date()
    return datetime.combine(col, time(12, 0), tzinfo=timezone.utc)


@pytest.fixture
def bd_category(db_session: Session, test_organization) -> ExpenseCategory:
    cat = ExpenseCategory(
        name="Depreciacion Reloj Unico",
        is_direct_expense=False,
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def bd_account(db_session: Session, test_organization) -> MoneyAccount:
    acc = MoneyAccount(
        name="Cuenta Reloj Unico",
        account_type="bank",
        current_balance=Decimal("5000000000"),
        initial_balance=Decimal("5000000000"),
        organization_id=test_organization.id,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


def _create_asset(client, org_headers, category, account, **overrides):
    """100M, cuota 1M, salvage 0, pagado de la cuenta."""
    payload = {
        "name": "Camion Reloj Unico",
        "asset_code": "RU-001",
        "purchase_date": "2026-01-01",
        "purchase_value": 100000000,
        "salvage_value": 0,
        "depreciation_rate": 1.0,
        "depreciation_start_date": "2026-01-01",
        "expense_category_id": str(category.id),
        "source_account_id": str(account.id),
    }
    payload.update(overrides)
    resp = client.post(BASE_URL + "/", json=payload, headers=org_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _balance(client, org_headers, as_of=None):
    params = {"as_of_date": as_of} if as_of else {}
    resp = client.get("/api/v1/reports/balance-sheet", params=params, headers=org_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestUnSoloRelojPorEvento:
    """🔴 Guardarrail: se sostienen a cualquier hora del dia."""

    def test_venta_disposed_at_cae_el_mismo_dia_que_su_movimiento(
        self, client, org_headers, bd_category, bd_account, db_session,
    ):
        """La invariante que faltaba: los dos campos que el mismo hecho deja
        escritos —el MM que mueve la caja y el `disposed_at` que gobierna el
        corte— tienen que caer en el MISMO dia de negocio."""
        asset = _create_asset(client, org_headers, bd_category, bd_account)
        resp = client.post(
            f"{BASE_URL}/{asset['id']}/sell",
            json={"sale_price": 130000000, "account_id": str(bd_account.id)},
            headers=org_headers,
        )
        assert resp.status_code == 201, resp.text

        db_session.expire_all()
        fa = db_session.get(FixedAsset, UUID(asset["id"]))
        mov = db_session.get(MoneyMovement, fa.sale_movement_id)

        assert fa.disposed_at.date() == mov.date.date(), (
            "disposed_at y el movimiento de la venta cayeron en dias distintos "
            "— el balance a esa fecha no va a cuadrar"
        )
        # Fecha de negocio, no instante: mediodia UTC (marca de `BusinessDate`)
        assert fa.disposed_at.astimezone(timezone.utc).hour == 12
        assert fa.disposed_at.date() == _business_today().date()

    def test_baja_disposed_at_cae_el_mismo_dia_que_su_depreciacion(
        self, client, org_headers, bd_category, bd_account, db_session,
    ):
        """Mismo guardarrail para `dispose()` (#21) — el bug es mas viejo que
        la venta: la depreciacion acelerada se fecha con el dia colombiano."""
        asset = _create_asset(client, org_headers, bd_category, bd_account)
        resp = client.post(
            f"{BASE_URL}/{asset['id']}/dispose",
            json={"reason": "Chatarrizado"},
            headers=org_headers,
        )
        assert resp.status_code == 200, resp.text

        db_session.expire_all()
        fa = db_session.get(FixedAsset, UUID(asset["id"]))
        dep = [d for d in fa.depreciations if d.is_active][-1]
        mov = db_session.get(MoneyMovement, dep.money_movement_id)

        assert fa.disposed_at.date() == mov.date.date()
        assert fa.disposed_at.astimezone(timezone.utc).hour == 12
        assert fa.disposed_at.date() == _business_today().date()


class TestBalanceCuadraElDiaDelEvento:
    """El sintoma que se veia: al corte del dia del evento, la plata y el
    activo tienen que moverse JUNTOS. (Solo discrimina dentro de la franja
    00-05 UTC; fuera de ella pasaba antes tambien.)"""

    def test_venta_al_corte_de_hoy_saca_el_activo_y_mete_la_plata(
        self, client, org_headers, bd_category, bd_account,
    ):
        asset = _create_asset(client, org_headers, bd_category, bd_account)
        hoy = _business_today().date().isoformat()
        antes = _balance(client, org_headers, hoy)

        resp = client.post(
            f"{BASE_URL}/{asset['id']}/sell",
            json={"sale_price": 130000000, "account_id": str(bd_account.id)},
            headers=org_headers,
        )
        assert resp.status_code == 201, resp.text

        despues = _balance(client, org_headers, hoy)
        # El activo sale por su valor en LIBROS (D1 de #88: el libro no se expensa)
        assert despues["assets"]["fixed_assets"] == antes["assets"]["fixed_assets"] - 100000000
        assert despues["assets"]["cash_and_bank"] == pytest.approx(
            antes["assets"]["cash_and_bank"] + 130000000, abs=1,
        )
        # Y el corte del dia ANTERIOR no se entera de nada
        ayer = (_business_today().date() - timedelta(days=1)).isoformat()
        bs_ayer = _balance(client, org_headers, ayer)
        assert bs_ayer["assets"]["fixed_assets"] == antes["assets"]["fixed_assets"]

    def test_baja_al_corte_de_hoy_saca_el_activo(
        self, client, org_headers, bd_category, bd_account,
    ):
        asset = _create_asset(client, org_headers, bd_category, bd_account)
        hoy = _business_today().date().isoformat()
        antes = _balance(client, org_headers, hoy)

        resp = client.post(
            f"{BASE_URL}/{asset['id']}/dispose",
            json={"reason": "Chatarrizado"},
            headers=org_headers,
        )
        assert resp.status_code == 200, resp.text

        despues = _balance(client, org_headers, hoy)
        assert despues["assets"]["fixed_assets"] == antes["assets"]["fixed_assets"] - 100000000
