"""Lectura de organization.settings (SAC E1, D3 del plan).

`settings` es un JSONB nullable en organizations: NULL = flags apagados y
parametros en default — las orgs existentes ejecutan exactamente el codigo
de hoy sin tocar sus filas. La escritura es REPLACE del dict completo y solo
via PATCH /system/organizations/{id} (superuser); ver OrgSettingsPayload.

⚠️ Contrato del CONSUMIDOR (watch-point QA, cierre E1 2026-07-16):
`transfer_tolerance_pct` viaja como FLOAT (H1 — JSONB round-tripea numeros
JSON; Decimal reventaria el write path). Al compararlo contra cantidades kg
(Decimal en todo el repo), convertir EN EL PUNTO DE LECTURA:

    tolerance = Decimal(str(get_org_setting(db, org_id, "transfer_tolerance_pct")))

La aritmetica `Decimal ± float` lanza TypeError (crash real) y
`Decimal('0.05') == 0.05` es False (representacion binaria).
"""
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.organization import Organization

# Defaults canonicos (v0.5 §11.2.8 + plan-ejecucion §1.1). El frontend
# (useOrgSettings) espeja estos mismos valores — mantener sincronizados.
SETTING_DEFAULTS: dict = {
    "kg_ledger_enabled": False,
    "two_step_transfers_enabled": False,
    "internal_maquila_enabled": False,
    "transfer_tolerance_pct": 0.05,
    "intersede_stale_days": 30,
    "aging_buckets": [30, 60, 90],
    # SAC E2 (D12): centros de distribucion Willard — "extensible sin migracion"
    # (v0.5 §6.5); pereira/medellin se agregan por system PATCH al confirmarse
    "willard_distribution_centers": ["baq", "bog", "monteria", "santa_marta", "motocosta"],
    # SAC Ciclo B (B2, F2 QA): sedes deterministas Willard — warehouse IDs como
    # STR (JSON-nativo, H1). None = sin configurar -> la validacion no aplica.
    # drosses: bodega unica obligatoria (Q-03/Q-05: siempre la planta Juan Mina).
    # postconsumo: default del selector (Q-05: Circunvalar, editable entre sedes
    # con cuenta willard_baterias — el frontend filtra por cuenta).
    "willard_sede_drosses": None,
    "willard_sede_postconsumo_default": None,
    # W1 (D4c): sede que FACTURA a Willard (Circunvalar). None = sin
    # configurar -> no se emite el par de reparto y la factura nace sin
    # bodega ($0 por sede). Default inerte, patron D1.
    "willard_sede_facturacion": None,
    # SAC #93 (D8): tolerancia del descuadre de entrada — FRACCION, no
    # porcentaje (igual que transfer_tolerance_pct). Dentro: aviso suave;
    # fuera: resaltado. JAMAS bloquea por monto (#17/#76).
    "inbound_discrepancy_tolerance_pct": 0.05,
}


def get_org_setting(db: Session, organization_id: UUID, key: str):
    """Valor efectivo de un setting de la org (o su default).

    Usa db.get() — PK lookup contra el identity map de la Session: llamadas
    repetidas en el mismo request no re-consultan la BD.
    """
    if key not in SETTING_DEFAULTS:
        raise KeyError(f"Setting desconocido: {key!r} — agregar a SETTING_DEFAULTS")

    org = db.get(Organization, organization_id)
    if org is None or not org.settings:
        return SETTING_DEFAULTS[key]

    value = org.settings.get(key)
    # Clave ausente o null explicito -> default (contrato OrgSettingsPayload)
    return SETTING_DEFAULTS[key] if value is None else value
