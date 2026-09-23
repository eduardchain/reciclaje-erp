"""
Entidades "[Impuestos] X" — IVA y retenciones de lo que SAC factura (CC-013 D4).

Hermano de `retention_entities.py`, y SEPARADO a proposito: la retefuente que
SAC le practica a un chatarrero es un PASIVO y la que Willard le practica a SAC
es un ACTIVO. Compartir entidad las netearia, y netearlas es un error contable,
no una preferencia (confirmado por QA).

RECONOCIMIENTO POR CODIGO, NUNCA POR TEXTO (D4b): la categoria lleva
`system_code='taxes'` y el get-or-create busca por ese codigo. Es el patron de
#58, que eligio codigo justamente porque un nombre es renombrable — y el repo
ya tiene un caso que clasifica por texto ("obligaci" en el nombre) que no
conviene imitar.

⚠️ El codigo se llama `taxes` y no `tax_advance`: UNA sola categoria alberga
las dos clases de entidad, la que debe y la que tiene a favor, y el SIGNO del
saldo decide la seccion del balance. Un codigo llamado `tax_advance` sobre una
categoria que tambien contiene el IVA por pagar miente al que lo lea despues.
Regla: el codigo nombra lo que la categoria ES, no el efecto que dispara.

⚠️ `behavior_type='liability'` (precedente #75) ancla la entidad al pasivo y la
deja oculta del multi-select del formulario de terceros por `HIDDEN_BEHAVIORS`
— o sea que la pantalla no ofrece una categoria que el servidor rechaza, que es
la clase de defecto de #97 y #104.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.third_party import ThirdParty
from app.services.retention_entities import normalize_entity_name

#: Codigo estable de la categoria de sistema. El reconocimiento va por acá.
TAX_CATEGORY_CODE = "taxes"
TAX_CATEGORY_NAME = "Impuestos"

#: Formato canonico de los nombres — propiedad de ESTE modulo.
TAX_ENTITY_NAMES = {
    "iva": "[Impuestos] IVA por Pagar",
    "retefuente": "[Impuestos] ReteFuente a Favor",
    "reteiva": "[Impuestos] ReteIVA a Favor",
}
ICA_PREFIX = "[Impuestos] ICA a Favor "

TAX_LABELS = {
    "iva": "IVA",
    "retefuente": "ReteFuente",
    "reteiva": "ReteIVA",
    "ica": "ICA",
}


def tax_entity_name(tax_type: str, municipality: Optional[str]) -> str:
    if tax_type == "ica":
        return f"{ICA_PREFIX}{(municipality or '').strip()}"
    return TAX_ENTITY_NAMES[tax_type]


def tax_label(tax_type: str, municipality: Optional[str] = None) -> str:
    label = TAX_LABELS.get(tax_type, tax_type)
    return f"{label} {municipality}" if municipality else label


def get_or_create_tax_category(db: Session, organization_id: UUID):
    """Categoria de sistema con `system_code='taxes'` — get-or-create POR CODIGO.

    El indice unico parcial `(organization_id, system_code) WHERE system_code
    IS NOT NULL` hace imposible la segunda fila con el mismo codigo (A1): #58
    dejo esa unicidad escrita como advertencia y ahi quedo.
    """
    from app.models.third_party_category import ThirdPartyCategory

    category = db.execute(
        select(ThirdPartyCategory).where(
            ThirdPartyCategory.organization_id == organization_id,
            ThirdPartyCategory.system_code == TAX_CATEGORY_CODE,
        )
    ).scalar_one_or_none()
    if category is None:
        category = ThirdPartyCategory(
            organization_id=organization_id,
            name=TAX_CATEGORY_NAME,
            behavior_type="liability",
            system_code=TAX_CATEGORY_CODE,
            is_active=True,
        )
        db.add(category)
        db.flush()
    return category


def _tax_candidates(db: Session, organization_id: UUID) -> list[ThirdParty]:
    return list(db.execute(
        select(ThirdParty).where(
            ThirdParty.organization_id == organization_id,
            ThirdParty.is_system_entity == True,  # noqa: E712
            ThirdParty.name.ilike("[Impuestos]%"),
        )
    ).scalars().all())


def resolve_tax_entity(
    db: Session, organization_id: UUID, tax_type: str,
    municipality: Optional[str] = None,
) -> ThirdParty:
    """Entidad '[Impuestos] X' — get-or-create idempotente.

    ICA: una entidad POR municipio, con matching sin acentos ni casing (H4 de
    #75, se persiste el display bonito de la primera vez).

    La asignacion de categoria se crea DIRECTO acá, sin pasar por
    `_sync_category_assignments` — que es el punto que el guard de D4d protege.
    Mismo reparto que #58: la entidad de sistema se siembra desde el codigo y
    los guards viven en los puntos de entrada del usuario.
    """
    from app.models.third_party_category import ThirdPartyCategoryAssignment

    display = tax_entity_name(tax_type, municipality)
    target = normalize_entity_name(display)

    for tp in _tax_candidates(db, organization_id):
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

    category = get_or_create_tax_category(db, organization_id)
    db.add(ThirdPartyCategoryAssignment(third_party_id=tp.id, category_id=category.id))
    db.flush()
    return tp
