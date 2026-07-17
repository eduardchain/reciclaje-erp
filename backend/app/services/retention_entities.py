"""
Entidades de retención "[Retenciones] X" — módulo compartido (paquete UX addendum §8).

Extraído de services/purchase.py (SAC E2 D9) para que lo consuman TANTO la
liquidación de compras (get-or-create al aplicar retenciones) COMO los endpoints
de gestión (GET/POST /third-parties/retention-entities: hogar en Pasivos +
selector de municipio ICA al liquidar).

Invariantes que NO se negocian (F3 QA):
- Matching H4 sin acentos ni casing ('Bogota' == 'Bogotá'), NFKD intacto.
- El formato canónico de nombres es propiedad de ESTE módulo (el GET lo parsea;
  nadie más construye esos strings).
- La categoría sistema `Retenciones` behavior_type='liability' ancla la entidad
  al pasivo del Balance y habilita su pago vía payment_to_supplier (#33).
"""
import unicodedata
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.third_party import ThirdParty

# Formato canónico (server-side, parseable por list_retention_entities)
RETENTION_ENTITY_NAMES = {
    "retefuente": "[Retenciones] ReteFuente",
    "reteiva": "[Retenciones] ReteIVA",
}
ICA_PREFIX = "[Retenciones] ICA "


def ica_entity_name(municipality: str) -> str:
    return f"{ICA_PREFIX}{municipality.strip()}"


def normalize_entity_name(name: str) -> str:
    """Matching sin acentos ni casing (H4 QA): 'Bogota' == 'Bogotá'."""
    return (
        unicodedata.normalize("NFKD", name)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .strip()
    )


def _retention_candidates(db: Session, organization_id: UUID) -> list[ThirdParty]:
    return list(db.execute(
        select(ThirdParty).where(
            ThirdParty.organization_id == organization_id,
            ThirdParty.is_system_entity == True,  # noqa: E712
            ThirdParty.name.ilike("[Retenciones]%"),
        )
    ).scalars().all())


def resolve_retention_entity(
    db: Session, organization_id: UUID, retention_type: str,
    municipality: Optional[str],
) -> ThirdParty:
    """Entidad sistema '[Retenciones] X' — get-or-create idempotente.
    ICA: una entidad POR municipio; matching sin acentos/casing (H4, se
    persiste el display bonito de la primera vez). Duplicacion bajo
    liquidaciones concurrentes aceptada (precedente D14-E1: maestros sin
    UNIQUE de BD). La categoria sistema behavior_type='liability' es la
    que ancla la entidad al pasivo del Balance y habilita su pago via
    payment_to_supplier (#33)."""
    from app.models.third_party_category import (
        ThirdPartyCategory,
        ThirdPartyCategoryAssignment,
    )

    if retention_type == "ica":
        display = ica_entity_name(municipality)
    else:
        display = RETENTION_ENTITY_NAMES[retention_type]
    target = normalize_entity_name(display)

    for tp in _retention_candidates(db, organization_id):
        if normalize_entity_name(tp.name) == target:
            return tp

    tp = ThirdParty(
        name=display,
        organization_id=organization_id,
        is_system_entity=True,
        is_active=True,
    )
    db.add(tp)
    db.flush()

    category = db.execute(
        select(ThirdPartyCategory).where(
            ThirdPartyCategory.organization_id == organization_id,
            ThirdPartyCategory.behavior_type == "liability",
            ThirdPartyCategory.name == "Retenciones",
        )
    ).scalar_one_or_none()
    if category is None:
        category = ThirdPartyCategory(
            organization_id=organization_id,
            name="Retenciones",
            behavior_type="liability",
            is_active=True,
        )
        db.add(category)
        db.flush()
    db.add(ThirdPartyCategoryAssignment(third_party_id=tp.id, category_id=category.id))
    db.flush()
    print(f"  🏛️ Entidad de retencion creada: {display}")
    return tp


def list_retention_entities(db: Session, organization_id: UUID) -> list[dict]:
    """Lista estructurada para el GET: parsea el formato canónico PROPIO.
    Orden: retefuente, reteiva, luego ICA por municipio asc. Nombres que no
    matchean el formato se omiten (defensivo — no deberían existir)."""
    type_by_name = {v: k for k, v in RETENTION_ENTITY_NAMES.items()}
    rows: list[dict] = []
    for tp in _retention_candidates(db, organization_id):
        if tp.name in type_by_name:
            rtype, municipality = type_by_name[tp.name], None
        elif tp.name.startswith(ICA_PREFIX):
            rtype, municipality = "ica", tp.name[len(ICA_PREFIX):]
        else:
            continue
        rows.append({
            "id": tp.id,
            "retention_type": rtype,
            "municipality": municipality,
            "name": tp.name,
            "current_balance": float(tp.current_balance),
            "is_active": tp.is_active,
        })
    order = {"retefuente": 0, "reteiva": 1, "ica": 2}
    rows.sort(key=lambda r: (order[r["retention_type"]], (r["municipality"] or "").lower()))
    return rows
