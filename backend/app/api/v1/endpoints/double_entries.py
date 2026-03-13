"""
REST API endpoints for double-entry (Pasa Mano) operations.

A double-entry operation represents buying from a supplier and immediately
selling to a customer without the material entering inventory.

Workflow de 2 pasos: registrar → liquidar.
"""
import logging
from datetime import date, datetime, time as dt_time, timedelta, timezone as tz
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_required_org_context
from app.models.double_entry import DoubleEntry
from app.schemas.double_entry import (
    DoubleEntryCreate,
    DoubleEntryFullUpdate,
    DoubleEntryLiquidateRequest,
    DoubleEntryResponse,
    PaginatedDoubleEntryResponse,
)
from app.services.double_entry import double_entry as double_entry_service

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================

def _enrich_double_entry_response(double_entry: DoubleEntry) -> dict:
    """
    Enrich double_entry object with joined data for response.

    Assumes double_entry was loaded with proper joinedload options
    (lines + materials, supplier, customer, sale.commissions).
    """
    lines_data = [
        {
            **line.__dict__,
            "total_purchase": line.total_purchase,
            "total_sale": line.total_sale,
            "profit": line.profit,
            "material_code": line.material.code if line.material else "",
            "material_name": line.material.name if line.material else "",
        }
        for line in double_entry.lines
    ]

    material_names = [line.material.name for line in double_entry.lines if line.material]

    return {
        **double_entry.__dict__,
        "lines": lines_data,
        "materials_summary": ", ".join(material_names),
        "total_purchase_cost": double_entry.total_purchase_cost,
        "total_sale_amount": double_entry.total_sale_amount,
        "profit": double_entry.profit,
        "profit_margin": double_entry.profit_margin,
        "supplier_name": double_entry.supplier.name if double_entry.supplier else None,
        "customer_name": double_entry.customer.name if double_entry.customer else None,
        "commissions": [
            {
                **comm.__dict__,
                "third_party_name": comm.third_party.name if comm.third_party else None,
            }
            for comm in (double_entry.sale.commissions if double_entry.sale else [])
        ],
    }


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "",
    response_model=DoubleEntryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar doble partida",
    description="""
    Registrar nueva doble partida (Pasa Mano).

    **Paso 1 — Sin efectos financieros:**
    - Crea Purchase + Sale en status='registered'
    - Crea SaleCommission records (sin MoneyMovement)
    - NO actualiza balances proveedor/cliente
    - NO crea movimientos de inventario

    **Para aplicar efectos financieros, usar PATCH /{id}/liquidate**
    """,
)
async def create_double_entry(
    double_entry_in: DoubleEntryCreate,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> DoubleEntryResponse:
    """Registrar nueva doble partida."""
    try:
        double_entry_obj = double_entry_service.create(
            db=db,
            obj_in=double_entry_in,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
        )

        # Reload with eager loading to get all relationships
        double_entry_obj = double_entry_service.get(
            db=db,
            double_entry_id=double_entry_obj.id,
            organization_id=org_context["organization_id"],
        )

        response_data = _enrich_double_entry_response(double_entry_obj)

        logger.info(
            f"Double-entry #{double_entry_obj.double_entry_number} registered by user {org_context['user_id']} "
            f"in org {org_context['organization_id']}"
        )

        return DoubleEntryResponse(**response_data)

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating double-entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Numero de doble partida duplicado. Reintente.",
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating double-entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error inesperado",
        )


@router.get(
    "",
    response_model=PaginatedDoubleEntryResponse,
    summary="Listar doble partidas",
    description="""
    Listado paginado de doble partidas con filtros.

    **Filtros:**
    - status: 'registered', 'liquidated' o 'cancelled'
    - material_id, supplier_id, customer_id
    - date_from, date_to
    - search: buscar en numero, notas, factura
    """,
)
async def list_double_entries(
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    status: Optional[str] = Query(None, description="Filter by status: 'registered', 'liquidated' or 'cancelled'"),
    material_id: Optional[UUID] = Query(None, description="Filter by material UUID"),
    supplier_id: Optional[UUID] = Query(None, description="Filter by supplier UUID"),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer UUID"),
    date_from: Optional[date] = Query(None, description="Filter by date from (inclusive)"),
    date_to: Optional[date] = Query(None, description="Filter by date to (inclusive)"),
    search: Optional[str] = Query(None, description="Search in number, names, notes, invoice"),
) -> PaginatedDoubleEntryResponse:
    """Listar doble partidas con filtros."""
    date_from_dt = datetime.combine(date_from, dt_time.min, tzinfo=tz.utc) if date_from else None
    date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc) if date_to else None
    double_entries, total = double_entry_service.get_multi(
        db=db,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
        status=status,
        material_id=material_id,
        supplier_id=supplier_id,
        customer_id=customer_id,
        date_from=date_from_dt,
        date_to=date_to_dt,
        search=search,
    )

    items = [
        DoubleEntryResponse(**_enrich_double_entry_response(de))
        for de in double_entries
    ]

    return PaginatedDoubleEntryResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{double_entry_id}",
    response_model=DoubleEntryResponse,
    summary="Obtener doble partida por UUID",
)
async def get_double_entry(
    double_entry_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> DoubleEntryResponse:
    """Obtener doble partida por UUID."""
    double_entry_obj = double_entry_service.get(
        db=db,
        double_entry_id=double_entry_id,
        organization_id=org_context["organization_id"],
    )

    if not double_entry_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doble partida no encontrada",
        )

    response_data = _enrich_double_entry_response(double_entry_obj)
    return DoubleEntryResponse(**response_data)


@router.get(
    "/by-number/{double_entry_number}",
    response_model=DoubleEntryResponse,
    summary="Obtener doble partida por numero secuencial",
)
async def get_double_entry_by_number(
    double_entry_number: int,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> DoubleEntryResponse:
    """Obtener doble partida por numero secuencial."""
    double_entry_obj = double_entry_service.get_by_number(
        db=db,
        double_entry_number=double_entry_number,
        organization_id=org_context["organization_id"],
    )

    if not double_entry_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Doble partida #{double_entry_number} no encontrada",
        )

    response_data = _enrich_double_entry_response(double_entry_obj)
    return DoubleEntryResponse(**response_data)


@router.get(
    "/supplier/{supplier_id}",
    response_model=PaginatedDoubleEntryResponse,
    summary="Listar doble partidas por proveedor",
)
async def list_double_entries_by_supplier(
    supplier_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> PaginatedDoubleEntryResponse:
    """Listar doble partidas por proveedor."""
    double_entries, total = double_entry_service.get_by_supplier(
        db=db,
        supplier_id=supplier_id,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
    )

    items = [
        DoubleEntryResponse(**_enrich_double_entry_response(de))
        for de in double_entries
    ]

    return PaginatedDoubleEntryResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/customer/{customer_id}",
    response_model=PaginatedDoubleEntryResponse,
    summary="Listar doble partidas por cliente",
)
async def list_double_entries_by_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> PaginatedDoubleEntryResponse:
    """Listar doble partidas por cliente."""
    double_entries, total = double_entry_service.get_by_customer(
        db=db,
        customer_id=customer_id,
        organization_id=org_context["organization_id"],
        skip=skip,
        limit=limit,
    )

    items = [
        DoubleEntryResponse(**_enrich_double_entry_response(de))
        for de in double_entries
    ]

    return PaginatedDoubleEntryResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.patch(
    "/{double_entry_id}/liquidate",
    response_model=DoubleEntryResponse,
    summary="Liquidar doble partida",
    description="""
    Liquidar doble partida registrada — confirmar precios y aplicar efectos financieros.

    **Paso 2 — Aplica efectos financieros:**
    - Opcionalmente ajustar precios de compra/venta por linea
    - Opcionalmente reemplazar comisiones
    - Actualiza balance proveedor (deuda aumenta)
    - Actualiza balance cliente (cuenta por cobrar aumenta)
    - Crea MoneyMovements 'commission_accrual' + actualiza balances comisionistas
    - Marca Purchase, Sale y DoubleEntry como 'liquidated'

    **Requiere:** status == 'registered'
    """,
)
async def liquidate_double_entry(
    double_entry_id: UUID,
    liquidate_request: DoubleEntryLiquidateRequest,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> DoubleEntryResponse:
    """Liquidar doble partida registrada."""
    try:
        double_entry_obj = double_entry_service.liquidate(
            db=db,
            double_entry_id=double_entry_id,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
            line_updates=liquidate_request.lines,
            commissions_data=liquidate_request.commissions,
        )

        # Reload with eager loading
        double_entry_obj = double_entry_service.get(
            db=db,
            double_entry_id=double_entry_obj.id,
            organization_id=org_context["organization_id"],
        )

        response_data = _enrich_double_entry_response(double_entry_obj)

        logger.info(
            f"Double-entry #{double_entry_obj.double_entry_number} liquidated by user {org_context['user_id']}"
        )

        return DoubleEntryResponse(**response_data)

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        logger.error(f"Error liquidating double-entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error inesperado",
        )


@router.patch(
    "/{double_entry_id}/cancel",
    response_model=DoubleEntryResponse,
    summary="Cancelar doble partida",
    description="""
    Cancelar doble partida y revertir efectos segun estado.

    **Si status='registered':** Cancelacion trivial (sin efectos financieros que revertir).
    **Si status='liquidated':** Revierte balances proveedor/cliente, anula comisiones causadas.
    """,
)
async def cancel_double_entry(
    double_entry_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> DoubleEntryResponse:
    """Cancelar doble partida."""
    try:
        double_entry_obj = double_entry_service.cancel(
            db=db,
            double_entry_id=double_entry_id,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
        )

        # Reload with eager loading
        double_entry_obj = double_entry_service.get(
            db=db,
            double_entry_id=double_entry_obj.id,
            organization_id=org_context["organization_id"],
        )

        response_data = _enrich_double_entry_response(double_entry_obj)

        logger.info(
            f"Double-entry #{double_entry_obj.double_entry_number} cancelled by user {org_context['user_id']}"
        )

        return DoubleEntryResponse(**response_data)

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling double-entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error inesperado",
        )


@router.patch(
    "/{double_entry_id}",
    response_model=DoubleEntryResponse,
    summary="Editar doble partida registrada",
    description="""
    Edicion completa de doble partida en estado 'registered'.

    **Permite cambiar:**
    - Proveedor, cliente
    - Fecha, factura, placa, notas
    - Lineas (materiales, cantidades, precios)
    - Comisiones

    **Requiere:** status == 'registered'
    """,
)
async def edit_double_entry(
    double_entry_id: UUID,
    double_entry_update: DoubleEntryFullUpdate,
    db: Session = Depends(get_db),
    org_context: dict = Depends(get_required_org_context),
) -> DoubleEntryResponse:
    """Editar doble partida registrada."""
    try:
        double_entry_obj = double_entry_service.edit(
            db=db,
            double_entry_id=double_entry_id,
            obj_in=double_entry_update,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
        )

        # Reload with eager loading
        double_entry_obj = double_entry_service.get(
            db=db,
            double_entry_id=double_entry_obj.id,
            organization_id=org_context["organization_id"],
        )

        response_data = _enrich_double_entry_response(double_entry_obj)

        return DoubleEntryResponse(**response_data)

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        logger.error(f"Error editing double-entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ocurrió un error inesperado",
        )
