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


def _parse_entity(tp: ThirdParty) -> Optional[tuple[str, Optional[str]]]:
    """Nombre canónico → (tipo, municipio). None si no matchea el formato."""
    type_by_name = {v: k for k, v in RETENTION_ENTITY_NAMES.items()}
    if tp.name in type_by_name:
        return type_by_name[tp.name], None
    if tp.name.startswith(ICA_PREFIX):
        return "ica", tp.name[len(ICA_PREFIX):]
    return None


_TYPE_ORDER = {"retefuente": 0, "reteiva": 1, "ica": 2}


def list_retention_rows(db: Session, organization_id: UUID) -> list[dict]:
    """GET unificado (plan v2 D-v2-1): UNIÓN de configs y entidades matcheadas
    por (tipo, municipio-normalizado). Filas:
    - config + entidad → completa (config_id, entity_id, %, saldo).
    - config sin entidad (aún sin uso) → entity_id NULL, saldo 0.0 — visible
      desde el día uno (resuelve el pre-crear ReteFuente/ReteIVA).
    - entidad sin config (pre-v2 / manual vieja) → config_id NULL, sin %.
    Varias configs del mismo tipo (conceptos F3) comparten UNA entidad — el
    acreedor es uno, la tarifa varía; cada fila muestra el saldo de SU entidad."""
    from app.models.retention_config import RetentionConfig

    entities: dict[tuple[str, Optional[str]], ThirdParty] = {}
    for tp in _retention_candidates(db, organization_id):
        parsed = _parse_entity(tp)
        if parsed:
            rtype, municipality = parsed
            entities[(rtype, normalize_entity_name(municipality) if municipality else None)] = tp

    configs = list(db.execute(
        select(RetentionConfig).where(
            RetentionConfig.organization_id == organization_id,
        )
    ).scalars().all())

    rows: list[dict] = []
    matched_keys: set[tuple[str, Optional[str]]] = set()
    for cfg in configs:
        key = (
            cfg.retention_type,
            normalize_entity_name(cfg.municipality) if cfg.municipality else None,
        )
        tp = entities.get(key)
        if tp is not None:
            matched_keys.add(key)
        rows.append({
            "config_id": cfg.id,
            "entity_id": tp.id if tp is not None else None,
            "retention_type": cfg.retention_type,
            "municipality": cfg.municipality,
            "concept": cfg.concept,
            "rate_pct": float(cfg.rate_pct),
            "name": tp.name if tp is not None else None,
            "current_balance": float(tp.current_balance) if tp is not None else 0.0,
            "is_active": cfg.is_active,
        })

    for key, tp in entities.items():
        if key in matched_keys:
            continue
        rtype, _ = key
        parsed = _parse_entity(tp)
        rows.append({
            "config_id": None,
            "entity_id": tp.id,
            "retention_type": rtype,
            "municipality": parsed[1] if parsed else None,
            "concept": None,
            "rate_pct": None,
            "name": tp.name,
            "current_balance": float(tp.current_balance),
            "is_active": tp.is_active,
        })

    rows.sort(key=lambda r: (
        _TYPE_ORDER[r["retention_type"]],
        (r["municipality"] or "").lower(),
        (r["concept"] or ""),  # NULL (general) primero
    ))
    return rows


def _norm_or_none(value: Optional[str]) -> Optional[str]:
    return normalize_entity_name(value) if value else None


def find_active_config(
    db: Session, organization_id: UUID, retention_type: str,
    municipality: Optional[str], concept: Optional[str],
):
    """Config activa que colisiona por (tipo, municipio, concepto) normalizados
    H4 — la unicidad vive en servicio (D14), no en BD."""
    from app.models.retention_config import RetentionConfig

    target = (_norm_or_none(municipality), _norm_or_none(concept))
    for cfg in db.execute(
        select(RetentionConfig).where(
            RetentionConfig.organization_id == organization_id,
            RetentionConfig.retention_type == retention_type,
            RetentionConfig.is_active == True,  # noqa: E712
        )
    ).scalars():
        if (_norm_or_none(cfg.municipality), _norm_or_none(cfg.concept)) == target:
            return cfg
    return None
