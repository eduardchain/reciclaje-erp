"""
Operaciones para FixedAsset (Activos Fijos con Depreciacion).

Flujo:
1. create(): Registrar activo fijo con valores de compra y depreciacion
2. apply_depreciation(): Aplicar UNA cuota de depreciacion mensual
3. apply_pending(): Aplicar depreciacion a TODOS los activos activos del mes
4. dispose(): Dar de baja con depreciacion acelerada si queda valor
5. update(): Editar activo (restringido si ya tiene depreciaciones)
6. revalue(): Revalorizar al alza/baja con contrapartida cuenta o tercero
7. annul_revaluation(): Anular revalorizacion (guard LIFO exacto)
8. sell(): Vender con contrapartida cuenta XOR tercero (ganancia/perdida al P&L)
9. annul_sale(): Anular la venta (revierte contrapartida, restaura status derivado)
"""
from datetime import date, datetime, time, timezone
from decimal import Decimal
from math import ceil
from typing import Optional, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.models.fixed_asset import FixedAsset, AssetDepreciation, AssetRevaluation
from app.models.expense_category import ExpenseCategory
from app.models.third_party import ThirdParty
from app.models.money_movement import MoneyMovement
from app.services.money_movement import money_movement as mm_service
from app.utils.dates import business_today as _business_today, business_today_noon


def business_today() -> datetime:
    """El dia de negocio de HOY a mediodia UTC — alias local de `business_today_noon`.

    UN SOLO RELOJ POR EVENTO: el `MoneyMovement` y el campo que los reportes
    usan como frontera (`disposed_at`) tienen que caer en el MISMO dia. Con el
    movimiento en el dia colombiano y el `disposed_at` en `now(timezone.utc)`,
    entre las 19:00 y 24:00 hora Colombia el balance a esa fecha mostraba la
    plata adentro y el activo todavia en libros. Ver CLAUDE.md, regla del
    reloj unico.

    Para timestamps de AUDITORIA (`applied_at`, `annulled_at`) y para ORDEN de
    eventos (guards LIFO) el reloj correcto sigue siendo
    `datetime.now(timezone.utc)`: son instantes reales, no dias.
    """
    return business_today_noon()


class CRUDFixedAsset:
    """Operaciones CRUD para activos fijos."""

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        db: Session,
        data,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> FixedAsset:
        """
        Registrar activo fijo con pago desde cuenta O a crédito con proveedor.

        1. Validar categoria de gasto
        2. Validar fuente de pago (cuenta O proveedor)
        3. Calcular depreciacion mensual y vida util
        4. Crear FixedAsset + MoneyMovement
        """
        # 0. Guard: UN sistema (Pasa Mano) no acepta asignacion compartida.
        # Validar aca (fuente) — las depreciaciones mensuales heredan esta asignacion.
        from app.services.business_unit import validate_not_shared_with_system_bu
        validate_not_shared_with_system_bu(
            db, organization_id,
            getattr(data, "applicable_business_unit_ids", None),
            field_label="gasto compartido (activo fijo)",
        )

        # 1. Validar categoria de gasto
        cat = db.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.id == data.expense_category_id,
                ExpenseCategory.organization_id == organization_id,
                ExpenseCategory.is_active == True,
            )
        ).scalar_one_or_none()
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoría de gasto no encontrada",
            )

        # 2. Validar fuente de pago (solo si NO es carga historica)
        is_historical = getattr(data, "historical_load", False)
        account = None
        supplier = None

        if not is_historical:
            if data.source_account_id:
                account = mm_service._validate_account(
                    db, data.source_account_id, organization_id,
                    require_funds=data.purchase_value,
                )
            else:
                from app.services.third_party import third_party as tp_service
                supplier = db.execute(
                    select(ThirdParty).where(
                        ThirdParty.id == data.supplier_id,
                        ThirdParty.organization_id == organization_id,
                        ThirdParty.is_active == True,
                    )
                ).scalar_one_or_none()
                if not supplier or not tp_service.has_behavior_type(db, supplier.id, ["material_supplier", "service_provider", "customer", "investor", "generic"]):
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Proveedor no encontrado",
                    )

        # 3. Calcular depreciacion
        monthly_depreciation = (
            data.purchase_value * (data.depreciation_rate / Decimal("100"))
        ).quantize(Decimal("0.01"))

        depreciable = data.purchase_value - data.salvage_value
        useful_life = ceil(float(depreciable / monthly_depreciation))

        # Normalizar applicable_business_unit_ids
        applicable_bu_ids = None
        if hasattr(data, 'applicable_business_unit_ids') and data.applicable_business_unit_ids:
            applicable_bu_ids = [str(uid) for uid in data.applicable_business_unit_ids]

        # 4. Crear activo
        accumulated = getattr(data, "accumulated_depreciation", Decimal("0")) or Decimal("0")
        asset = FixedAsset(
            organization_id=organization_id,
            name=data.name,
            asset_code=data.asset_code,
            notes=data.notes,
            purchase_date=data.purchase_date,
            depreciation_start_date=data.depreciation_start_date,
            purchase_value=data.purchase_value,
            salvage_value=data.salvage_value,
            current_value=data.purchase_value - accumulated,
            accumulated_depreciation=accumulated,
            depreciation_rate=data.depreciation_rate,
            monthly_depreciation=monthly_depreciation,
            useful_life_months=useful_life,
            expense_category_id=data.expense_category_id,
            third_party_id=data.supplier_id if not is_historical else None,
            business_unit_id=getattr(data, 'business_unit_id', None),
            applicable_business_unit_ids=applicable_bu_ids,
            status="active",
            created_by=user_id,
        )
        db.add(asset)
        db.flush()

        # 5. Crear movimiento según fuente (skip para carga historica)
        if not is_historical:
            movement_date = datetime.combine(
                data.purchase_date, time(12, 0), tzinfo=timezone.utc
            )

            if account:
                movement = mm_service._create_movement(
                    db=db,
                    organization_id=organization_id,
                    movement_type="asset_payment",
                    amount=data.purchase_value,
                    account_id=data.source_account_id,
                    date=movement_date,
                    description=f"Compra activo: {data.name}",
                    user_id=user_id,
                    third_party_id=None,
                )
                account.current_balance -= data.purchase_value
            else:
                movement = mm_service._create_movement(
                    db=db,
                    organization_id=organization_id,
                    movement_type="asset_purchase",
                    amount=data.purchase_value,
                    account_id=None,
                    date=movement_date,
                    description=f"Compra activo a crédito: {data.name}",
                    user_id=user_id,
                    third_party_id=data.supplier_id,
                )
                supplier.current_balance -= data.purchase_value

            asset.purchase_movement_id = movement.id

        db.commit()
        db.refresh(asset)
        return asset

    # ------------------------------------------------------------------
    # Depreciation
    # ------------------------------------------------------------------

    def apply_depreciation(
        self,
        db: Session,
        asset_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
        period: Optional[str] = None,
    ) -> FixedAsset:
        """
        Aplicar UNA cuota de depreciacion.

        1. Validar activo activo
        2. Determinar periodo (default: mes actual Colombia)
        3. Validar no duplicado, no futuro
        4. Calcular monto (ultima cuota ajustada)
        5. Crear MoneyMovement depreciation_expense
        6. Crear AssetDepreciation
        7. Actualizar activo
        """
        asset = self.get(db, asset_id, organization_id)

        if asset.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede depreciar: activo en estado '{asset.status}'",
            )

        # Determinar periodo
        if not period:
            col_today = _business_today()
            period = col_today.strftime("%Y-%m")

        # Validar periodo no futuro
        col_today = _business_today()
        current_period = col_today.strftime("%Y-%m")
        if period > current_period:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede depreciar un período futuro: {period}",
            )

        # Validar depreciation_start_date
        start_period = asset.depreciation_start_date.strftime("%Y-%m")
        if period < start_period:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El período {period} es anterior al inicio de depreciación ({start_period})",
            )

        # Validar duplicado
        existing = db.execute(
            select(AssetDepreciation).where(
                AssetDepreciation.fixed_asset_id == asset.id,
                AssetDepreciation.period == period,
                AssetDepreciation.is_active == True,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe depreciación para el período {period}",
            )

        # Calcular monto
        remaining = asset.current_value - asset.salvage_value
        if remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El activo ya alcanzó su valor residual",
            )

        if remaining <= asset.monthly_depreciation:
            # Ultima cuota: ajustar para llegar exacto a salvage_value
            amount = remaining
        else:
            amount = asset.monthly_depreciation

        # Fecha del movimiento: primer dia del periodo a mediodia UTC
        year, month = int(period[:4]), int(period[5:7])
        movement_date = datetime.combine(
            date(year, month, 1), time(12, 0), tzinfo=timezone.utc
        )

        # Crear MoneyMovement depreciation_expense (hereda UN del activo)
        movement = mm_service._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="depreciation_expense",
            amount=amount,
            account_id=None,
            date=movement_date,
            description=f"Depreciación {asset.name} - {period}",
            third_party_id=None,
            expense_category_id=asset.expense_category_id,
            user_id=user_id,
            business_unit_id=asset.business_unit_id,
            applicable_business_unit_ids=asset.applicable_business_unit_ids,
        )

        # Numero de depreciacion
        dep_count = db.execute(
            select(func.count()).where(
                AssetDepreciation.fixed_asset_id == asset.id,
                AssetDepreciation.is_active == True,
            )
        ).scalar() or 0
        dep_number = dep_count + 1

        # Actualizar activo
        new_accumulated = asset.accumulated_depreciation + amount
        new_current = asset.current_value - amount

        # Crear AssetDepreciation
        depreciation = AssetDepreciation(
            fixed_asset_id=asset.id,
            depreciation_number=dep_number,
            period=period,
            amount=amount,
            accumulated_after=new_accumulated,
            current_value_after=new_current,
            money_movement_id=movement.id,
            applied_at=datetime.now(timezone.utc),
            applied_by=user_id,
        )
        db.add(depreciation)

        asset.accumulated_depreciation = new_accumulated
        asset.current_value = new_current

        # Verificar si se completó
        if new_current <= asset.salvage_value:
            asset.status = "fully_depreciated"

        db.commit()
        db.refresh(asset)
        return asset

    # ------------------------------------------------------------------
    # Apply Pending (batch)
    # ------------------------------------------------------------------

    def apply_pending(
        self,
        db: Session,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> List[dict]:
        """
        Aplicar depreciacion pendiente a todos los activos activos del mes actual.

        Solo procesa activos cuyo depreciation_start_date <= primer dia del mes actual.
        """
        col_today = _business_today()
        current_period = col_today.strftime("%Y-%m")
        first_of_month = col_today.replace(day=1)

        # Buscar activos activos con fecha de inicio <= hoy
        # (si start_date cae dentro del mes actual, el activo es elegible)
        assets = db.execute(
            select(FixedAsset).where(
                FixedAsset.organization_id == organization_id,
                FixedAsset.status == "active",
                FixedAsset.depreciation_start_date <= col_today,
            )
        ).scalars().all()

        results = []
        for asset in assets:
            # Verificar si ya tiene depreciacion del mes
            existing = db.execute(
                select(AssetDepreciation).where(
                    AssetDepreciation.fixed_asset_id == asset.id,
                    AssetDepreciation.period == current_period,
                    AssetDepreciation.is_active == True,
                )
            ).scalar_one_or_none()

            if existing:
                continue

            # Aplicar depreciacion
            try:
                updated = self.apply_depreciation(
                    db, asset.id, organization_id, user_id, current_period
                )
                results.append({
                    "asset_id": str(asset.id),
                    "asset_name": asset.name,
                    "amount": float(updated.monthly_depreciation
                                    if updated.status == "active"
                                    else updated.current_value),
                    "new_status": updated.status,
                })
            except HTTPException:
                # Saltar activos con errores (ej: ya completado)
                continue

        return results

    # ------------------------------------------------------------------
    # Dispose
    # ------------------------------------------------------------------

    def dispose(
        self,
        db: Session,
        asset_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
        reason: str = "",
    ) -> FixedAsset:
        """
        Dar de baja un activo.

        Si queda valor pendiente (current_value > salvage_value),
        crea una depreciacion acelerada por la diferencia.
        """
        asset = self.get(db, asset_id, organization_id)

        if asset.status == "disposed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El activo ya está dado de baja",
            )

        # Un solo reloj para todo el evento (ver `business_today`)
        movement_date = business_today()

        remaining = asset.current_value - asset.salvage_value
        if remaining > 0:
            # Depreciacion acelerada — periodo con sufijo "B" (baja) para evitar conflicto unique
            disposal_period = movement_date.strftime("%Y-%m") + "B"

            movement = mm_service._create_movement(
                db=db,
                organization_id=organization_id,
                movement_type="depreciation_expense",
                amount=remaining,
                account_id=None,
                date=movement_date,
                description=f"Depreciación acelerada (baja): {asset.name}",
                third_party_id=None,
                expense_category_id=asset.expense_category_id,
                user_id=user_id,
                business_unit_id=asset.business_unit_id,
                applicable_business_unit_ids=asset.applicable_business_unit_ids,
            )

            dep_count = db.execute(
                select(func.count()).where(
                    AssetDepreciation.fixed_asset_id == asset.id,
                    AssetDepreciation.is_active == True,
                )
            ).scalar() or 0

            depreciation = AssetDepreciation(
                fixed_asset_id=asset.id,
                depreciation_number=dep_count + 1,
                period=disposal_period,
                amount=remaining,
                accumulated_after=asset.accumulated_depreciation + remaining,
                current_value_after=asset.salvage_value,
                money_movement_id=movement.id,
                applied_at=datetime.now(timezone.utc),
                applied_by=user_id,
            )
            db.add(depreciation)

            asset.accumulated_depreciation += remaining
            asset.current_value = asset.salvage_value

        asset.status = "disposed"
        # Frontera de corte (`_fa_existed_at_cutoff`), NO un timestamp: mismo
        # dia que el movimiento de la baja
        asset.disposed_at = movement_date
        asset.disposed_by = user_id
        asset.disposal_reason = reason

        db.commit()
        db.refresh(asset)
        return asset

    # ------------------------------------------------------------------
    # Venta (plan venta-activos-fijos)
    # ------------------------------------------------------------------

    def sell(
        self,
        db: Session,
        asset_id: UUID,
        organization_id: UUID,
        data,
        user_id: Optional[UUID] = None,
    ) -> tuple[FixedAsset, list[str]]:
        """
        Vender un activo: contrapartida cuenta (entra dinero) XOR tercero (CxC).

        D1 — la venta NO expensa el remanente (a diferencia de dispose): el
        valor en libros se da de baja contra el precio, current_value queda
        CONGELADO (exactitud as-of por construccion, #41/#61/#67) y la
        diferencia precio - libro se persiste en sale_gain (linea P&L
        "Ganancia/Perdida por Venta de Activos", gobernada por el status
        del MM enlazado — patron oversell #65/#66).
        Fecha del evento SIEMPRE hoy — anti back-dating (#62/#67).
        Retorna (asset, warnings) — patron #17: avisar, no bloquear.
        """
        asset = self.get(db, asset_id, organization_id)

        if asset.status not in ("active", "fully_depreciated"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede vender: activo en estado '{asset.status}'",
            )

        # Contrapartida XOR (el schema valida el XOR; aca se validan entidades)
        account = None
        third_party = None
        if data.account_id:
            account = mm_service._validate_account(
                db, data.account_id, organization_id,
            )
        else:
            from app.services.third_party import third_party as tp_service
            third_party = db.execute(
                select(ThirdParty).where(
                    ThirdParty.id == data.third_party_id,
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_active == True,
                )
            ).scalar_one_or_none()
            # Comprador: cualquier tercero menos provision/liability (espejo #32,
            # misma regla que la contrapartida de revalorizacion)
            if not third_party or not tp_service.has_behavior_type(
                db, third_party.id,
                ["material_supplier", "service_provider", "customer", "investor", "generic"],
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tercero no encontrado",
                )

        # Warning informativo (no bloquea, #17/#76): vender con depreciaciones
        # pendientes congela el libro como esta — ganancia mayor a la que
        # tendria aplicando primero los meses pendientes.
        warnings: list[str] = []
        pending = self._pending_months(asset)
        if pending > 0:
            warnings.append(
                f"El activo tiene {pending} mes(es) de depreciación sin aplicar. "
                f"La venta usa el valor en libros actual (${asset.current_value:,.0f}); "
                f"aplicar la depreciación pendiente primero reduciría el libro y "
                f"aumentaría la ganancia registrada."
            )

        book_value = asset.current_value
        sale_gain = (data.sale_price - book_value).quantize(Decimal("0.01"))

        # Fecha del evento: SIEMPRE hoy (patron dispose/revalue) — anti back-dating.
        # Un solo reloj para todo el evento (ver `business_today`)
        movement_date = business_today()

        # MM de contrapartida — lleva el PRECIO, no la ganancia.
        # ⚠️ Signos alineados con los 4 sign maps derivados + INFLOW_TYPES.
        if account:
            movement = mm_service._create_movement(
                db=db,
                organization_id=organization_id,
                movement_type="asset_sale_collection",
                amount=data.sale_price,
                account_id=data.account_id,
                date=movement_date,
                description=f"Venta de activo: {asset.name}",
                user_id=user_id,
                third_party_id=None,
                notes=data.notes,
            )
            account.current_balance += data.sale_price
        else:
            movement = mm_service._create_movement(
                db=db,
                organization_id=organization_id,
                movement_type="asset_sale_receivable",
                amount=data.sale_price,
                account_id=None,
                date=movement_date,
                description=f"Venta de activo: {asset.name}",
                user_id=user_id,
                third_party_id=data.third_party_id,
                notes=data.notes,
            )
            third_party.current_balance += data.sale_price

        db.flush()

        # D1: current_value NO se toca (libro congelado); cero depreciaciones.
        asset.sale_price = data.sale_price
        asset.sale_gain = sale_gain
        asset.sale_movement_id = movement.id
        asset.status = "disposed"
        # Frontera de corte (`_fa_existed_at_cutoff`), NO un timestamp: el
        # MISMO dia que el MM del precio, o el balance a esa fecha muestra la
        # plata adentro y el activo todavia en libros
        asset.disposed_at = movement_date
        asset.disposed_by = user_id
        asset.disposal_reason = "Venta"

        db.commit()
        db.refresh(asset)
        return asset, warnings

    def annul_sale(
        self,
        db: Session,
        asset_id: UUID,
        organization_id: UUID,
        reason: str,
        user_id: Optional[UUID] = None,
    ) -> FixedAsset:
        """
        Anular la venta: revierte la contrapartida y restaura el activo.

        Guard LIFO defensivo (barandilla — un activo vendido no genera
        eventos, imposible por construccion): sin depreciaciones ni
        revalorizaciones activas posteriores a la venta. El status se
        RESTAURA DERIVADO de current_value vs salvage_value (criterio #67
        "estados derivados") — D1 garantiza que el libro quedo intacto.
        Las columnas sale_* quedan como rastro: el MM anulado las saca del
        P&L (la linea filtra por MM.status='confirmed').
        """
        asset = self.get(db, asset_id, organization_id)

        if asset.status != "disposed" or not asset.sale_movement_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El activo no tiene una venta vigente para anular",
            )

        movement = db.get(MoneyMovement, asset.sale_movement_id)
        if not movement or movement.status != "confirmed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La venta ya está anulada",
            )

        # Barandilla LIFO (ver docstring).
        # ⚠️ Ordenar eventos es una pregunta de INSTANTES, no de dias: se
        # compara contra el `created_at` del movimiento de la venta (cuando se
        # registro de verdad), no contra `disposed_at`, que es la FECHA DE
        # NEGOCIO de la venta (mediodia UTC, ver `business_today`). Mezclarlos
        # daba un falso positivo: un `applied_at` de hace un minuto es
        # "posterior" a un mediodia que ya paso, y el guard bloqueaba
        # anulaciones legitimas.
        sold_at = movement.created_at or asset.disposed_at
        later_dep = db.execute(
            select(func.count()).where(
                AssetDepreciation.fixed_asset_id == asset.id,
                AssetDepreciation.is_active == True,
                AssetDepreciation.applied_at > sold_at,
            )
        ).scalar() or 0
        later_reval = db.execute(
            select(func.count()).where(
                AssetRevaluation.fixed_asset_id == asset.id,
                AssetRevaluation.is_active == True,
                AssetRevaluation.applied_at > sold_at,
            )
        ).scalar() or 0
        if later_dep or later_reval:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede anular: el activo tiene eventos posteriores a la venta",
            )

        now = datetime.now(timezone.utc)

        # Revertir contrapartida (efecto opuesto exacto)
        if movement.account_id:
            from app.models.money_account import MoneyAccount
            acc = db.get(MoneyAccount, movement.account_id)
            if acc:
                acc.current_balance -= movement.amount
        elif movement.third_party_id:
            tp = db.get(ThirdParty, movement.third_party_id)
            if tp:
                tp.current_balance -= movement.amount
        movement.status = "annulled"
        movement.annulled_at = now
        movement.annulled_by = user_id
        movement.annulled_reason = f"Anulación de venta de activo: {reason}"

        # Restaurar: status derivado del libro congelado (D1)
        if asset.current_value <= asset.salvage_value:
            asset.status = "fully_depreciated"
        else:
            asset.status = "active"
        asset.disposed_at = None
        asset.disposed_by = None
        asset.disposal_reason = None

        db.commit()
        db.refresh(asset)
        return asset

    def _pending_months(self, asset: FixedAsset) -> int:
        """Meses de depreciacion vencidos sin aplicar (aprox informativa para warning)."""
        if asset.status != "active" or asset.monthly_depreciation <= 0:
            return 0
        if asset.current_value <= asset.salvage_value:
            return 0
        today = _business_today()
        start = asset.depreciation_start_date
        # Meses contables completos transcurridos desde el inicio
        elapsed = (today.year - start.year) * 12 + (today.month - start.month)
        if today.day >= start.day:
            elapsed += 1
        applied = len([d for d in asset.depreciations if d.is_active]) if asset.depreciations else 0
        remaining_value = asset.current_value - asset.salvage_value
        max_remaining = ceil(float(remaining_value / asset.monthly_depreciation))
        return max(0, min(elapsed - applied, max_remaining))

    # ------------------------------------------------------------------
    # Revalorizacion (requerimiento D — mejora capitalizable / recuperacion)
    # ------------------------------------------------------------------

    def revalue(
        self,
        db: Session,
        asset_id: UUID,
        organization_id: UUID,
        data,
        user_id: Optional[UUID] = None,
    ) -> FixedAsset:
        """
        Revalorizar un activo fijo al alza o a la baja.

        La contrapartida SIEMPRE es una cuenta (dinero sale/entra) o un tercero
        (deuda a favor/en contra) — cero efecto en P&L, cero patrimonio.
        Alza: current_value += amount, opcionalmente extiende vida util.
        Baja: current_value -= amount (nunca por debajo de salvage_value).
        Recalcula la cuota: (valor_nuevo - salvage) / meses_restantes.
        La fecha del evento es SIEMPRE hoy (sin input) — anti back-dating (#62).
        """
        asset = self.get(db, asset_id, organization_id)

        if asset.status not in ("active", "fully_depreciated"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede revalorizar: activo en estado '{asset.status}'",
            )

        is_increase = data.revaluation_type == "increase"
        amount = data.amount
        months_extended = data.months_extended if is_increase else 0

        # Validaciones de negocio
        if not is_increase:
            depreciable = asset.current_value - asset.salvage_value
            if depreciable <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El activo ya está en su valor residual — no hay valor que bajar",
                )
            if amount > depreciable:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"La baja (${amount}) supera el valor depreciable restante "
                        f"(${depreciable}). El valor no puede caer bajo el residual."
                    ),
                )

        # Contrapartida: cuenta XOR tercero (el schema ya valida el XOR)
        account = None
        third_party = None
        if data.source_account_id:
            account = mm_service._validate_account(
                db, data.source_account_id, organization_id,
                # Solo el alza saca dinero de la cuenta
                require_funds=amount if is_increase else None,
            )
        else:
            from app.services.third_party import third_party as tp_service
            third_party = db.execute(
                select(ThirdParty).where(
                    ThirdParty.id == data.third_party_id,
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_active == True,
                )
            ).scalar_one_or_none()
            # Mismas reglas que el proveedor de activos (#32): todo menos provision/liability
            if not third_party or not tp_service.has_behavior_type(
                db, third_party.id,
                ["material_supplier", "service_provider", "customer", "investor", "generic"],
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tercero no encontrado",
                )

        # Snapshot + recalculo de cuota sobre meses restantes
        value_before = asset.current_value
        monthly_before = asset.monthly_depreciation
        salvage = asset.salvage_value

        if value_before > salvage and monthly_before > 0:
            remaining_before = ceil(float((value_before - salvage) / monthly_before))
        else:
            remaining_before = 0
        remaining_after = remaining_before + months_extended

        value_after = value_before + amount if is_increase else value_before - amount

        if value_after > salvage:
            if remaining_after < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "El activo no tiene meses restantes de depreciación. "
                        "Especifique months_extended >= 1 para extender la vida útil."
                    ),
                )
            monthly_after = (
                (value_after - salvage) / Decimal(remaining_after)
            ).quantize(Decimal("0.01"))
        else:
            # Baja que deja el valor exactamente en el residual
            monthly_after = monthly_before

        # Fecha del evento: SIEMPRE hoy (patron dispose) — anti back-dating
        col_today = _business_today()
        period = col_today.strftime("%Y-%m")
        movement_date = business_today_noon()  # mismo dia que col_today, por construccion
        now = datetime.now(timezone.utc)

        label = "alza" if is_increase else "baja"
        # MM de contrapartida — el efecto de saldo lo aplica este metodo (patron create()).
        # ⚠️ El signo debe coincidir EXACTO con los 4 sign maps derivados
        # (reports as-of x2, endpoint statement x2) y los frozensets INFLOW/OUTFLOW.
        if account:
            mt = "asset_revaluation_payment" if is_increase else "asset_devaluation_collection"
            movement = mm_service._create_movement(
                db=db,
                organization_id=organization_id,
                movement_type=mt,
                amount=amount,
                account_id=data.source_account_id,
                date=movement_date,
                description=f"Revalorización activo ({label}): {asset.name}",
                user_id=user_id,
                third_party_id=None,
                notes=data.reason,
            )
            account.current_balance += -amount if is_increase else amount
        else:
            mt = "asset_revaluation_credit" if is_increase else "asset_devaluation_receivable"
            movement = mm_service._create_movement(
                db=db,
                organization_id=organization_id,
                movement_type=mt,
                amount=amount,
                account_id=None,
                date=movement_date,
                description=f"Revalorización activo ({label}): {asset.name}",
                user_id=user_id,
                third_party_id=data.third_party_id,
                notes=data.reason,
            )
            third_party.current_balance += -amount if is_increase else amount

        db.flush()

        revaluation = AssetRevaluation(
            organization_id=organization_id,
            fixed_asset_id=asset.id,
            revaluation_type=data.revaluation_type,
            amount=amount,
            months_extended=months_extended,
            value_before=value_before,
            value_after=value_after,
            monthly_before=monthly_before,
            monthly_after=monthly_after,
            period=period,
            money_movement_id=movement.id,
            reason=data.reason,
            applied_at=now,
            applied_by=user_id,
        )
        db.add(revaluation)

        # Actualizar activo
        asset.current_value = value_after
        asset.monthly_depreciation = monthly_after
        if months_extended:
            asset.useful_life_months += months_extended

        # Transiciones de estado
        if is_increase and asset.status == "fully_depreciated" and value_after > salvage:
            asset.status = "active"
        elif not is_increase and value_after <= salvage:
            asset.status = "fully_depreciated"

        db.commit()
        db.refresh(asset)
        return asset

    def annul_revaluation(
        self,
        db: Session,
        asset_id: UUID,
        revaluation_id: UUID,
        organization_id: UUID,
        reason: str,
        user_id: Optional[UUID] = None,
    ) -> FixedAsset:
        """
        Anular una revalorizacion, revirtiendo exactamente sus efectos.

        Guard LIFO: solo se puede anular si NO existe ningun evento activo
        POSTERIOR (depreciacion O revalorizacion). Sin esto, restaurar los
        snapshots value_before/monthly_before pisaria el recalculo de eventos
        posteriores, y el merge as-of (H1) leeria snapshots obsoletos.
        A diferencia del guard retirado en Fase 5 (#66), aqui el ledger es
        COMPLETO (todo evento que mueve current_value queda registrado) —
        el bloqueo es exacto por construccion, no un falso permiso.
        """
        asset = self.get(db, asset_id, organization_id)

        if asset.status not in ("active", "fully_depreciated"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede anular revalorizaciones de un activo '{asset.status}'",
            )

        revaluation = db.execute(
            select(AssetRevaluation).where(
                AssetRevaluation.id == revaluation_id,
                AssetRevaluation.fixed_asset_id == asset.id,
                AssetRevaluation.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not revaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Revalorización no encontrada",
            )
        if not revaluation.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La revalorización ya está anulada",
            )

        # Guard LIFO: eventos activos posteriores
        later_dep = db.execute(
            select(func.count()).where(
                AssetDepreciation.fixed_asset_id == asset.id,
                AssetDepreciation.is_active == True,
                AssetDepreciation.applied_at > revaluation.applied_at,
            )
        ).scalar() or 0
        later_reval = db.execute(
            select(func.count()).where(
                AssetRevaluation.fixed_asset_id == asset.id,
                AssetRevaluation.is_active == True,
                AssetRevaluation.applied_at > revaluation.applied_at,
            )
        ).scalar() or 0
        if later_dep or later_reval:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No se puede anular: el activo tiene depreciaciones o "
                    "revalorizaciones posteriores. Anule primero los eventos "
                    "más recientes (o cancele el activo completo)."
                ),
            )

        now = datetime.now(timezone.utc)
        is_increase = revaluation.revaluation_type == "increase"

        # Revertir el MM de contrapartida (efecto opuesto exacto)
        movement = db.get(MoneyMovement, revaluation.money_movement_id)
        if movement and movement.status == "confirmed":
            if movement.account_id:
                from app.models.money_account import MoneyAccount
                acc = db.get(MoneyAccount, movement.account_id)
                if acc:
                    # payment saco dinero → devolver; collection metio → sacar
                    acc.current_balance += movement.amount if is_increase else -movement.amount
            elif movement.third_party_id:
                tp = db.get(ThirdParty, movement.third_party_id)
                if tp:
                    # credit bajo su balance → subir; receivable subio → bajar
                    tp.current_balance += movement.amount if is_increase else -movement.amount
            movement.status = "annulled"
            movement.annulled_at = now
            movement.annulled_by = user_id
            movement.annulled_reason = f"Anulación de revalorización: {reason}"

        # Restaurar snapshots (exacto — garantizado por el guard LIFO)
        asset.current_value = revaluation.value_before
        asset.monthly_depreciation = revaluation.monthly_before
        if revaluation.months_extended:
            asset.useful_life_months -= revaluation.months_extended

        # Transiciones de estado inversas
        if asset.current_value <= asset.salvage_value:
            asset.status = "fully_depreciated"
        else:
            asset.status = "active"

        revaluation.is_active = False
        revaluation.annulled_at = now
        revaluation.annulled_by = user_id
        revaluation.annulled_reason = reason

        db.commit()
        db.refresh(asset)
        return asset

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(
        self,
        db: Session,
        asset_id: UUID,
        organization_id: UUID,
        data,
    ) -> FixedAsset:
        """
        Actualizar activo fijo.

        Si tiene depreciaciones: solo name, asset_code, notes.
        Si no tiene: tambien campos financieros.
        """
        asset = self.get(db, asset_id, organization_id)

        if asset.status == "disposed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede editar un activo dado de baja",
            )

        # Contar depreciaciones
        dep_count = db.execute(
            select(func.count()).where(
                AssetDepreciation.fixed_asset_id == asset.id,
                AssetDepreciation.is_active == True,
            )
        ).scalar() or 0

        # Campos siempre editables
        if data.name is not None:
            asset.name = data.name
        if data.asset_code is not None:
            asset.asset_code = data.asset_code
        if data.notes is not None:
            asset.notes = data.notes

        # Campos financieros solo si no hay depreciaciones
        financial_fields = ["purchase_value", "salvage_value", "depreciation_rate", "expense_category_id"]
        has_financial = any(getattr(data, f, None) is not None for f in financial_fields)

        has_accumulated = asset.accumulated_depreciation > 0
        if has_financial and (dep_count > 0 or has_accumulated):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pueden modificar valores financieros después de aplicar depreciaciones. Solo se permite editar nombre, código y notas.",
            )

        if dep_count == 0 and not has_accumulated:
            if data.expense_category_id is not None:
                # Validar categoria
                cat = db.execute(
                    select(ExpenseCategory).where(
                        ExpenseCategory.id == data.expense_category_id,
                        ExpenseCategory.organization_id == organization_id,
                        ExpenseCategory.is_active == True,
                    )
                ).scalar_one_or_none()
                if not cat:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Categoría de gasto no encontrada",
                    )
                asset.expense_category_id = data.expense_category_id

            if data.purchase_value is not None:
                asset.purchase_value = data.purchase_value
                # Solo actualizar current_value si cambia el valor de compra
                if data.purchase_value != asset.current_value:
                    asset.current_value = data.purchase_value

            if data.salvage_value is not None:
                asset.salvage_value = data.salvage_value

            if data.depreciation_rate is not None:
                asset.depreciation_rate = data.depreciation_rate

            # Recalcular si cambio algun valor financiero
            if any(getattr(data, f, None) is not None for f in ["purchase_value", "salvage_value", "depreciation_rate"]):
                pv = asset.purchase_value
                sv = asset.salvage_value
                rate = asset.depreciation_rate

                if pv <= sv:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El valor de compra debe ser mayor al valor residual",
                    )

                monthly = (pv * (rate / Decimal("100"))).quantize(Decimal("0.01"))
                depreciable = pv - sv
                useful_life = ceil(float(depreciable / monthly))

                asset.monthly_depreciation = monthly
                asset.useful_life_months = useful_life

        db.commit()
        db.refresh(asset)
        return asset

    # ------------------------------------------------------------------
    # Cancel (revertir completamente)
    # ------------------------------------------------------------------

    def cancel(
        self,
        db: Session,
        asset_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> FixedAsset:
        """
        Cancelar activo fijo, revirtiendo atomicamente todas las depreciaciones
        y el movimiento de pago original.

        A diferencia de dispose (baja), cancel revierte los efectos financieros.
        """
        asset = self.get(db, asset_id, organization_id)

        if asset.status in ("disposed", "cancelled"):
            msg = "dado de baja" if asset.status == "disposed" else "cancelado"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"El activo ya esta {msg}",
            )

        now = datetime.now(timezone.utc)

        # 1. Anular movimientos de depreciacion (no tienen efecto financiero)
        depreciations = db.execute(
            select(AssetDepreciation)
            .where(
                AssetDepreciation.fixed_asset_id == asset.id,
                AssetDepreciation.is_active == True,
            )
            .order_by(AssetDepreciation.depreciation_number.desc())
        ).scalars().all()

        for dep in depreciations:
            if dep.money_movement_id:
                mov = db.get(MoneyMovement, dep.money_movement_id)
                if mov and mov.status == "confirmed":
                    mov.status = "annulled"
                    mov.annulled_at = now
                    mov.annulled_by = user_id
                    mov.annulled_reason = f"Cancelacion de activo: {asset.name}"
            dep.is_active = False

        # 1b. Revertir revalorizaciones activas (los efectos de saldo son sumas
        # independientes — el orden no importa; el activo se cancela entero)
        revaluations = db.execute(
            select(AssetRevaluation).where(
                AssetRevaluation.fixed_asset_id == asset.id,
                AssetRevaluation.is_active == True,
            )
        ).scalars().all()

        for reval in revaluations:
            is_increase = reval.revaluation_type == "increase"
            mov = db.get(MoneyMovement, reval.money_movement_id)
            if mov and mov.status == "confirmed":
                if mov.account_id:
                    from app.models.money_account import MoneyAccount
                    acc = db.get(MoneyAccount, mov.account_id)
                    if acc:
                        acc.current_balance += mov.amount if is_increase else -mov.amount
                elif mov.third_party_id:
                    tp = db.get(ThirdParty, mov.third_party_id)
                    if tp:
                        tp.current_balance += mov.amount if is_increase else -mov.amount
                mov.status = "annulled"
                mov.annulled_at = now
                mov.annulled_by = user_id
                mov.annulled_reason = f"Cancelacion de activo: {asset.name}"
            reval.is_active = False
            reval.annulled_at = now
            reval.annulled_by = user_id
            reval.annulled_reason = f"Cancelacion de activo: {asset.name}"

        # 2. Revertir movimiento de pago original
        if asset.purchase_movement_id:
            payment_mov = db.get(MoneyMovement, asset.purchase_movement_id)
            if payment_mov and payment_mov.status == "confirmed":
                # Revertir efecto financiero
                if payment_mov.movement_type == "asset_payment" and payment_mov.account_id:
                    from app.models.money_account import MoneyAccount
                    account = db.get(MoneyAccount, payment_mov.account_id)
                    if account:
                        account.current_balance += payment_mov.amount
                elif payment_mov.movement_type == "asset_purchase" and payment_mov.third_party_id:
                    tp = db.get(ThirdParty, payment_mov.third_party_id)
                    if tp:
                        tp.current_balance += payment_mov.amount

                payment_mov.status = "annulled"
                payment_mov.annulled_at = now
                payment_mov.annulled_by = user_id
                payment_mov.annulled_reason = f"Cancelacion de activo: {asset.name}"

        # 3. Marcar activo como cancelado (reusa campos de disposal)
        asset.status = "cancelled"
        # Aca SI es un timestamp de auditoria y no una frontera: los
        # `cancelled` se excluyen del corte SIEMPRE, sin mirar la fecha
        # (735c2c3: "nunca existio"). Por eso no pasa por `business_today()`.
        asset.disposed_at = now
        asset.disposed_by = user_id
        asset.disposal_reason = "Cancelado"

        db.commit()
        db.refresh(asset)
        return asset

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(
        self,
        db: Session,
        asset_id: UUID,
        organization_id: UUID,
    ) -> FixedAsset:
        """Obtener activo fijo con depreciaciones y relaciones."""
        result = db.execute(
            select(FixedAsset)
            .options(
                joinedload(FixedAsset.depreciations),
                joinedload(FixedAsset.revaluations),
                joinedload(FixedAsset.expense_category),
                joinedload(FixedAsset.third_party),
            )
            .where(
                FixedAsset.id == asset_id,
                FixedAsset.organization_id == organization_id,
            )
        ).unique().scalar_one_or_none()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Activo fijo no encontrado",
            )
        return result

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ):
        """Listar activos fijos con filtro opcional por status."""
        base = select(FixedAsset).where(
            FixedAsset.organization_id == organization_id,
        )
        if status_filter:
            base = base.where(FixedAsset.status == status_filter)

        count_q = select(func.count()).select_from(base.subquery())
        total = db.execute(count_q).scalar() or 0

        items = db.execute(
            base.options(
                joinedload(FixedAsset.expense_category),
                joinedload(FixedAsset.third_party),
                # revalued_total se computa en _build_response también para el
                # listado — sin eager load seria un lazy-load N+1 por activo
                joinedload(FixedAsset.revaluations),
            )
            .order_by(FixedAsset.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).unique().scalars().all()

        return items, total


fixed_asset = CRUDFixedAsset()
