"""
Servicio KgLedger — cuentas paralelas en kg de plomo (SAC E2).

Plan: docs/planes/plan-sac-e2-kgledger-inbound.md (D6/D14/D16).
Saldo = SUM(delta_kg) WHERE status='confirmed' — sin snapshot materializado
(patron #16). Statement con fila de apertura real de la ventana (fix #55
desde el dia cero). Los movimientos de negocio (postconsumo/drosses) los
emite services/inbound_order.py — aqui solo manual_adjustment (D1).
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.third_party import ThirdParty
from app.models.warehouse import Warehouse
from app.schemas.kg_ledger import (
    KgLedgerAccountCreate,
    KgLedgerAccountResponse,
    KgLedgerAccountUpdate,
    KgLedgerMovementManualCreate,
    KgLedgerStatementResponse,
    KgLedgerStatementRow,
    KgLedgerSummaryAccount,
    KgLedgerSummaryResponse,
)

# Reglas de coherencia por tipo (v0.5 §11.1.1) — espejo amistoso de los CHECKs
# de BD (E1): el servicio responde 422 legible ANTES del IntegrityError.
_WILLARD_TYPES = {"willard_baterias", "willard_drosses"}
_INTERNAL_TYPES = {"intersede", "intra_horno", "crisol"}
_WAREHOUSE_REQUIRED = {"willard_baterias", "intra_horno", "crisol"}


def _err(detail: str, code: int = status.HTTP_422_UNPROCESSABLE_ENTITY):
    return HTTPException(status_code=code, detail=detail)


class KgLedgerService:
    # ------------------------------------------------------------------ #
    # Balances (helper compartido)                                        #
    # ------------------------------------------------------------------ #
    def balances(
        self,
        db: Session,
        organization_id: UUID,
        as_of: Optional[datetime] = None,
    ) -> dict[UUID, Decimal]:
        """SUM(delta_kg) confirmed por cuenta, opcionalmente a un corte (#41:
        los anulados NO cuentan sin importar fecha)."""
        q = (
            select(KgLedgerMovement.account_id, func.sum(KgLedgerMovement.delta_kg))
            .where(
                KgLedgerMovement.organization_id == organization_id,
                KgLedgerMovement.status == "confirmed",
            )
            .group_by(KgLedgerMovement.account_id)
        )
        if as_of is not None:
            q = q.where(KgLedgerMovement.transaction_date <= as_of)
        return {row[0]: row[1] or Decimal("0") for row in db.execute(q).all()}

    def account_balance(self, db: Session, organization_id: UUID, account_id: UUID) -> Decimal:
        return self.balances(db, organization_id).get(account_id, Decimal("0"))

    # ------------------------------------------------------------------ #
    # Cuentas                                                             #
    # ------------------------------------------------------------------ #
    def _get_account(self, db: Session, organization_id: UUID, account_id: UUID) -> KgLedgerAccount:
        acc = db.execute(
            select(KgLedgerAccount)
            .options(joinedload(KgLedgerAccount.warehouse), joinedload(KgLedgerAccount.third_party))
            .where(
                KgLedgerAccount.id == account_id,
                KgLedgerAccount.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if acc is None:
            raise _err("Cuenta kg no encontrada", status.HTTP_404_NOT_FOUND)
        return acc

    def _to_response(self, acc: KgLedgerAccount, balance: Decimal) -> KgLedgerAccountResponse:
        return KgLedgerAccountResponse(
            id=acc.id,
            code=acc.code,
            display_name=acc.display_name,
            account_type=acc.account_type,
            warehouse_id=acc.warehouse_id,
            warehouse_name=acc.warehouse.name if acc.warehouse else None,
            third_party_id=acc.third_party_id,
            third_party_name=acc.third_party.name if acc.third_party else None,
            tolerance_kg=acc.tolerance_kg,
            current_balance_kg=balance,
            is_active=acc.is_active,
            created_at=acc.created_at,
        )

    def list_accounts(
        self,
        db: Session,
        organization_id: UUID,
        account_type: Optional[str] = None,
        is_active: Optional[bool] = True,
    ) -> list[KgLedgerAccountResponse]:
        q = (
            select(KgLedgerAccount)
            .options(joinedload(KgLedgerAccount.warehouse), joinedload(KgLedgerAccount.third_party))
            .where(KgLedgerAccount.organization_id == organization_id)
            .order_by(KgLedgerAccount.account_type, KgLedgerAccount.code)
        )
        if account_type:
            q = q.where(KgLedgerAccount.account_type == account_type)
        if is_active is not None:
            q = q.where(KgLedgerAccount.is_active == is_active)
        accounts = db.execute(q).scalars().all()
        bals = self.balances(db, organization_id)
        return [self._to_response(a, bals.get(a.id, Decimal("0"))) for a in accounts]

    def create_account(
        self, db: Session, organization_id: UUID, data: KgLedgerAccountCreate
    ) -> KgLedgerAccountResponse:
        # Coherencia tipo <-> FKs (422 legible, D6)
        if data.account_type in _WILLARD_TYPES and data.third_party_id is None:
            raise _err("Las cuentas Willard requieren un tercero (Willard)")
        if data.account_type in _INTERNAL_TYPES and data.third_party_id is not None:
            raise _err("Las cuentas internas (intersede/horno/crisol) no llevan tercero")
        if data.account_type in _WAREHOUSE_REQUIRED and data.warehouse_id is None:
            raise _err(
                "Este tipo de cuenta requiere sede (sub-saldo por sede para Willard Baterias; "
                "sede fisica para horno/crisol)"
            )

        # FKs pertenecen a la org
        if data.warehouse_id is not None:
            wh = db.get(Warehouse, data.warehouse_id)
            if wh is None or wh.organization_id != organization_id:
                raise _err("Bodega no encontrada", status.HTTP_404_NOT_FOUND)
        if data.third_party_id is not None:
            tp = db.get(ThirdParty, data.third_party_id)
            if tp is None or tp.organization_id != organization_id:
                raise _err("Tercero no encontrado", status.HTTP_404_NOT_FOUND)

        # Unicidades amistosas (los UNIQUE de BD de E1 son la red final)
        dup_code = db.execute(
            select(KgLedgerAccount.id).where(
                KgLedgerAccount.organization_id == organization_id,
                KgLedgerAccount.code == data.code,
            )
        ).first()
        if dup_code:
            raise _err(f"Ya existe una cuenta con codigo '{data.code}'")
        dup_type = db.execute(
            select(KgLedgerAccount.code).where(
                KgLedgerAccount.organization_id == organization_id,
                KgLedgerAccount.account_type == data.account_type,
                KgLedgerAccount.warehouse_id.is_(None)
                if data.warehouse_id is None
                else KgLedgerAccount.warehouse_id == data.warehouse_id,
            )
        ).first()
        if dup_type:
            raise _err(
                f"Ya existe una cuenta '{data.account_type}' para esa sede "
                f"(codigo {dup_type[0]}) — la misma cuenta logica no se duplica"
            )

        acc = KgLedgerAccount(
            organization_id=organization_id,
            code=data.code,
            display_name=data.display_name,
            account_type=data.account_type,
            warehouse_id=data.warehouse_id,
            third_party_id=data.third_party_id,
            tolerance_kg=data.tolerance_kg,
            is_active=True,
        )
        db.add(acc)
        db.commit()
        db.refresh(acc)
        return self._to_response(acc, Decimal("0"))

    def update_account(
        self, db: Session, organization_id: UUID, account_id: UUID, data: KgLedgerAccountUpdate
    ) -> KgLedgerAccountResponse:
        acc = self._get_account(db, organization_id, account_id)
        balance = self.account_balance(db, organization_id, account_id)

        if data.is_active is False and acc.is_active and balance != 0:
            raise _err(
                f"No se puede desactivar una cuenta con saldo distinto de cero "
                f"({balance} kg) — ajuste el saldo primero (espejo regla de cuentas de dinero)"
            )
        if data.display_name is not None:
            acc.display_name = data.display_name
        if data.tolerance_kg is not None:
            acc.tolerance_kg = data.tolerance_kg
        if data.is_active is not None:
            acc.is_active = data.is_active
        db.commit()
        db.refresh(acc)
        return self._to_response(acc, balance)

    # ------------------------------------------------------------------ #
    # Statement / summary                                                 #
    # ------------------------------------------------------------------ #
    def statement(
        self,
        db: Session,
        organization_id: UUID,
        account_id: UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        status_filter: str = "confirmed",
    ) -> KgLedgerStatementResponse:
        acc = self._get_account(db, organization_id, account_id)
        if date_from is None:
            date_from = datetime.now(timezone.utc) - timedelta(days=90)

        movements = db.execute(
            select(KgLedgerMovement)
            .where(
                KgLedgerMovement.organization_id == organization_id,
                KgLedgerMovement.account_id == account_id,
            )
            .order_by(KgLedgerMovement.transaction_date, KgLedgerMovement.created_at)
        ).scalars().all()

        # Pasada unica sobre TODOS los eventos (fix #55): lo confirmado anterior
        # a la ventana acumula en opening; los anulados jamas mueven saldo. El
        # saldo corrido avanza con TODO confirmado de la ventana, se liste o no
        # (un anulado listado con status_filter='all' muestra el saldo sin el).
        opening = Decimal("0")
        current = Decimal("0")
        running = Decimal("0")
        rows: list[KgLedgerStatementRow] = []
        for m in movements:
            confirmed = m.status == "confirmed"
            if confirmed:
                current += m.delta_kg
            if m.transaction_date < date_from:
                if confirmed:
                    opening += m.delta_kg
                continue
            if date_to is not None and m.transaction_date > date_to:
                continue
            if confirmed:
                running += m.delta_kg
            if status_filter != "all" and m.status != status_filter:
                continue
            rows.append(
                KgLedgerStatementRow(
                    id=m.id,
                    account_id=m.account_id,
                    delta_kg=m.delta_kg,
                    transaction_date=m.transaction_date,
                    description=m.description,
                    source_type=m.source_type,
                    source_id=m.source_id,
                    inventory_movement_id=m.inventory_movement_id,
                    conversion_formula_snapshot=m.conversion_formula_snapshot,
                    status=m.status,
                    annulled_reason=m.annulled_reason,
                    annulled_at=m.annulled_at,
                    created_at=m.created_at,
                    balance_after_kg=opening + running,
                )
            )

        return KgLedgerStatementResponse(
            account=self._to_response(acc, current),
            opening_balance_kg=opening,
            movements=rows,
            current_balance_kg=current,
        )

    def summary(
        self,
        db: Session,
        organization_id: UUID,
        as_of: Optional[datetime] = None,
    ) -> KgLedgerSummaryResponse:
        accounts = db.execute(
            select(KgLedgerAccount)
            .options(joinedload(KgLedgerAccount.warehouse))
            .where(
                KgLedgerAccount.organization_id == organization_id,
                KgLedgerAccount.is_active.is_(True),
            )
            .order_by(KgLedgerAccount.account_type, KgLedgerAccount.code)
        ).scalars().all()

        bals = self.balances(db, organization_id, as_of=as_of)

        last_q = (
            select(
                KgLedgerMovement.account_id,
                func.max(KgLedgerMovement.transaction_date),
            )
            .where(
                KgLedgerMovement.organization_id == organization_id,
                KgLedgerMovement.status == "confirmed",
            )
            .group_by(KgLedgerMovement.account_id)
        )
        if as_of is not None:
            last_q = last_q.where(KgLedgerMovement.transaction_date <= as_of)
        last_map = {row[0]: row[1] for row in db.execute(last_q).all()}

        items: list[KgLedgerSummaryAccount] = []
        totals = {
            "willard": Decimal("0"),
            "intersede": Decimal("0"),
            "intra_horno": Decimal("0"),
            "crisol": Decimal("0"),
        }
        for a in accounts:
            bal = bals.get(a.id, Decimal("0"))
            items.append(
                KgLedgerSummaryAccount(
                    account_id=a.id,
                    code=a.code,
                    display_name=a.display_name,
                    account_type=a.account_type,
                    warehouse_id=a.warehouse_id,
                    warehouse_name=a.warehouse.name if a.warehouse else None,
                    balance_kg=bal,
                    tolerance_kg=a.tolerance_kg,
                    last_movement_at=last_map.get(a.id),
                    is_active=a.is_active,
                )
            )
            if a.account_type in _WILLARD_TYPES:
                totals["willard"] += bal
            elif a.account_type in totals:
                totals[a.account_type] += bal

        return KgLedgerSummaryResponse(
            accounts=items,
            total_willard_kg=totals["willard"],
            total_intersede_kg=totals["intersede"],
            total_intra_horno_kg=totals["intra_horno"],
            total_crisol_kg=totals["crisol"],
        )

    # ------------------------------------------------------------------ #
    # Movimiento manual + anulacion (D1/D16)                              #
    # ------------------------------------------------------------------ #
    def create_manual_movement(
        self,
        db: Session,
        organization_id: UUID,
        user_id: UUID,
        data: KgLedgerMovementManualCreate,
    ) -> KgLedgerMovement:
        acc = self._get_account(db, organization_id, data.account_id)
        if not acc.is_active:
            raise _err("La cuenta esta inactiva")

        mov = KgLedgerMovement(
            organization_id=organization_id,
            account_id=acc.id,
            delta_kg=data.delta_kg,
            transaction_date=data.transaction_date,
            description=f"{data.description} — Motivo: {data.reason}",
            source_type="manual_adjustment",
            source_id=None,
            created_by=user_id,
            status="confirmed",
        )
        db.add(mov)
        db.commit()
        db.refresh(mov)
        return mov

    def annul_movement(
        self,
        db: Session,
        organization_id: UUID,
        user_id: UUID,
        movement_id: UUID,
        reason: str,
    ) -> KgLedgerMovement:
        mov = db.execute(
            select(KgLedgerMovement).where(
                KgLedgerMovement.id == movement_id,
                KgLedgerMovement.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if mov is None:
            raise _err("Movimiento no encontrado", status.HTTP_404_NOT_FOUND)
        if mov.source_type != "manual_adjustment":
            # D16 — patron #67: anular desde el modulo dueño del evento
            raise _err(
                "Este movimiento lo emitio una operacion de negocio — anulelo desde "
                "su documento origen (orden de recepcion, traslado, etc.)"
            )
        if mov.status != "confirmed":
            raise _err("El movimiento ya esta anulado")

        mov.status = "annulled"
        mov.annulled_reason = reason
        mov.annulled_by = user_id
        mov.annulled_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(mov)
        return mov


kg_ledger_service = KgLedgerService()
