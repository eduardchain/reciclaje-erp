"""
Endpoints de listas de precios por proveedor (SAC, item 7 del ciclo Entradas).

🔴 TODO este router va gateado por `require_org_flag("kg_ledger_enabled")` — 403
incluso para admins. No es una comodidad: es lo que sostiene la premisa central
del diseño. Los precios de lista viven en la tabla COMPARTIDA `price_lists` con
`price_list_group_id NULL = lista general`, y la no-regresion de las 3 empresas
cliente es "esa columna esta en NULL en todas sus filas, para siempre". Si el
gate viviera solo en la pantalla, un admin de otra org podria llegar por API,
crear una lista y escribir la columna — y ahi la premisa deja de ser cierta.
Con el gate, el "para siempre" es una propiedad del sistema y no una promesa.

Sin permisos nuevos: reusa `materials.view_prices` / `materials.edit_prices`,
que ya gobiernan las rutas de precios (el administrador del sistema las tiene —
Hugo, Q-23).
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org_flag, require_permission
from app.schemas.price_list import PriceTableResponse
from app.schemas.price_list_group import (
    PriceListGroupCreate,
    PriceListGroupResponse,
    PriceListGroupUpdate,
    PriceListGroupsResponse,
    SeedResultResponse,
    SetMembersRequest,
    SupplierMembershipsResponse,
)
from app.services.price_list import price_list
from app.services.price_list_group import price_list_group_service

router = APIRouter(dependencies=[Depends(require_org_flag("kg_ledger_enabled"))])


@router.get("", response_model=PriceListGroupsResponse)
def list_groups(
    include_inactive: bool = Query(False, description="Incluir listas desactivadas"),
    org_context: dict = Depends(require_permission("materials.view_prices")),
    db: Session = Depends(get_db),
):
    """Listas de precios de la organizacion, con sus conteos."""
    items = price_list_group_service.list_groups(
        db=db,
        organization_id=org_context["organization_id"],
        include_inactive=include_inactive,
    )
    return PriceListGroupsResponse(items=items)


@router.post("", response_model=SeedResultResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: PriceListGroupCreate,
    org_context: dict = Depends(require_permission("materials.edit_prices")),
    db: Session = Depends(get_db),
):
    """
    Crear una lista, opcionalmente sembrada desde la general (Q-26).

    El sembrado existe porque sin lista no hay precio sugerido (D3): el dia que
    se enciende la funcion, sin sembrar, TODOS los proveedores quedan sin
    sugerencia de golpe.
    """
    group, seeded, assigned, skipped = price_list_group_service.create(
        db=db,
        obj_in=payload,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    [item] = [
        g for g in price_list_group_service.list_groups(
            db, org_context["organization_id"], include_inactive=True
        ) if g["id"] == group.id
    ]
    return SeedResultResponse(
        group=PriceListGroupResponse(**item),
        seeded_prices=seeded,
        assigned_suppliers=assigned,
        skipped_suppliers=skipped,
    )


@router.get("/suppliers", response_model=SupplierMembershipsResponse)
def list_supplier_memberships(
    org_context: dict = Depends(require_permission("materials.view_prices")),
    db: Session = Depends(get_db),
):
    """
    Proveedores de material con la lista a la que pertenecen HOY.

    La pantalla lo usa para avisar el conflicto ("este ya esta en la Lista B")
    ANTES de guardar, en vez de chocar contra el UNIQUE en el submit.
    """
    return SupplierMembershipsResponse(
        items=price_list_group_service.list_supplier_memberships(
            db=db, organization_id=org_context["organization_id"]
        )
    )


@router.patch("/{group_id}", response_model=PriceListGroupResponse)
def update_group(
    group_id: UUID,
    payload: PriceListGroupUpdate,
    org_context: dict = Depends(require_permission("materials.edit_prices")),
    db: Session = Depends(get_db),
):
    """Renombrar o activar/desactivar. Los precios de la lista no se tocan aca."""
    group = price_list_group_service.update(
        db=db,
        group_id=group_id,
        obj_in=payload,
        organization_id=org_context["organization_id"],
    )
    [item] = [
        g for g in price_list_group_service.list_groups(
            db, org_context["organization_id"], include_inactive=True
        ) if g["id"] == group.id
    ]
    return PriceListGroupResponse(**item)


@router.get("/{group_id}/table", response_model=PriceTableResponse)
def get_group_table(
    group_id: UUID,
    org_context: dict = Depends(require_permission("materials.view_prices")),
    db: Session = Depends(get_db),
):
    """
    Hoja de calculo de una lista: TODOS los materiales activos, con precio o
    vacios (Q-21 — la lista trae el catalogo completo y el usuario decide a
    cuales les pone precio).
    """
    price_list_group_service.get_or_404(db, group_id, org_context["organization_id"])
    return price_list.get_table(
        db=db,
        organization_id=org_context["organization_id"],
        group_id=group_id,
    )


@router.put("/{group_id}/members", response_model=SupplierMembershipsResponse)
def set_members(
    group_id: UUID,
    payload: SetMembersRequest,
    org_context: dict = Depends(require_permission("materials.edit_prices")),
    db: Session = Depends(get_db),
):
    """
    Reemplaza los proveedores de la lista (D12: la asignacion se hace DESDE la
    lista — "para esta lista son estos, estos y estos proveedores").

    Un proveedor que venia de otra lista **se mueve**: la unicidad es de la base.
    """
    price_list_group_service.set_members(
        db=db,
        group_id=group_id,
        third_party_ids=payload.third_party_ids,
        organization_id=org_context["organization_id"],
    )
    return SupplierMembershipsResponse(
        items=price_list_group_service.list_supplier_memberships(
            db=db, organization_id=org_context["organization_id"]
        )
    )
