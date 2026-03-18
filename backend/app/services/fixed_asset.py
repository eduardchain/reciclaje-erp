"""
Operaciones para FixedAsset (Activos Fijos con Depreciacion).

Flujo:
1. create(): Registrar activo fijo con valores de compra y depreciacion
2. apply_depreciation(): Aplicar UNA cuota de depreciacion mensual
3. apply_pending(): Aplicar depreciacion a TODOS los activos activos del mes
4. dispose(): Dar de baja con depreciacion acelerada si queda valor
5. update(): Editar activo (restringido si ya tiene depreciaciones)
"""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from math import ceil
from typing import Optional, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.models.fixed_asset import FixedAsset, AssetDepreciation
from app.models.expense_category import ExpenseCategory
from app.models.third_party import ThirdParty
from app.models.money_movement import MoneyMovement
from app.services.money_movement import money_movement as mm_service


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

        # 2. Validar fuente de pago
        account = None
        supplier = None

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
        asset = FixedAsset(
            organization_id=organization_id,
            name=data.name,
            asset_code=data.asset_code,
            notes=data.notes,
            purchase_date=data.purchase_date,
            depreciation_start_date=data.depreciation_start_date,
            purchase_value=data.purchase_value,
            salvage_value=data.salvage_value,
            current_value=data.purchase_value,
            accumulated_depreciation=Decimal("0"),
            depreciation_rate=data.depreciation_rate,
            monthly_depreciation=monthly_depreciation,
            useful_life_months=useful_life,
            expense_category_id=data.expense_category_id,
            third_party_id=data.supplier_id,
            business_unit_id=getattr(data, 'business_unit_id', None),
            applicable_business_unit_ids=applicable_bu_ids,
            status="active",
            created_by=user_id,
        )
        db.add(asset)
        db.flush()

        # 5. Crear movimiento según fuente
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
            col_today = datetime.now(ZoneInfo("America/Bogota")).date()
            period = col_today.strftime("%Y-%m")

        # Validar periodo no futuro
        col_today = datetime.now(ZoneInfo("America/Bogota")).date()
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
        col_today = datetime.now(ZoneInfo("America/Bogota")).date()
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

        remaining = asset.current_value - asset.salvage_value
        if remaining > 0:
            # Depreciacion acelerada — periodo con sufijo "B" (baja) para evitar conflicto unique
            col_today = datetime.now(ZoneInfo("America/Bogota")).date()
            disposal_period = col_today.strftime("%Y-%m") + "B"

            movement_date = datetime.combine(
                col_today, time(12, 0), tzinfo=timezone.utc
            )

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
        asset.disposed_at = datetime.now(timezone.utc)
        asset.disposed_by = user_id
        asset.disposal_reason = reason

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

        if has_financial and dep_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pueden modificar valores financieros después de aplicar depreciaciones. Solo se permite editar nombre, código y notas.",
            )

        if dep_count == 0:
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
            )
            .order_by(FixedAsset.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).unique().scalars().all()

        return items, total


fixed_asset = CRUDFixedAsset()
