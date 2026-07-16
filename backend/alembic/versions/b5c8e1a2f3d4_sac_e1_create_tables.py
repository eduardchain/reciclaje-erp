"""SAC E1 Migracion A: 13 tablas nuevas (plan-sac-e1-configuracion.md §3.1)

Fundaciones de datos SAC: dominio kg/tarifas (kg_ledger_accounts,
kg_ledger_movements, material_conversion_formulas, service_tariffs,
kg_ledger_reconciliation_seals), panel de excepciones (discrepancy_tasks,
daily_ok_seals), captura y planta (inbound_orders + lines, furnace_charges,
crucible_charges) y maestros de flota (drivers, vehicles).

Solo CREATE TABLE + indices — cero cambios a tablas existentes, cero seeds
(D8). Los CHECKs/UNIQUEs viven TAMBIEN en los modelos (D13: paridad
create_all <-> migraciones; la BD de test se recrea desde los modelos).
FKs sin nombre explicito -> PostgreSQL asigna el default (<tabla>_<col>_fkey),
identico a create_all — requisito del schema-diff H3.

NULLS NOT DISTINCT del unique de kg_ledger_accounts requiere PG15+
(dev/test/prod = PG16).

Revision ID: b5c8e1a2f3d4
Revises: a4317e2cd050
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'b5c8e1a2f3d4'
down_revision = 'a4317e2cd050'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. service_tariffs (antes que Migracion B: money_movements.tariff_id la referencia) ---
    op.create_table(
        'service_tariffs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('tariff_code', sa.String(length=48), nullable=False,
                  comment='maquila_willard | maquila_intersede_cv_jm | maquila_crisol | '
                          'flete_willard_bog_baq | flete_willard_planta_planta'),
        sa.Column('unit_price_cop', sa.Numeric(precision=12, scale=2), nullable=False,
                  comment='Precio unitario en pesos colombianos'),
        sa.Column('unit', sa.String(length=24), nullable=False,
                  comment='per_kg_lead | per_kg_battery | per_unit'),
        sa.Column('notes', sa.String(length=500), nullable=True,
                  comment='Contexto del cambio (renegociacion IPC, cambio contractual)'),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.CheckConstraint('unit_price_cop > 0', name='ck_service_tariffs_price_positive'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_service_tariffs_organization_id', 'service_tariffs',
                    ['organization_id'], unique=False)
    op.create_index('ix_st_code_current', 'service_tariffs',
                    ['organization_id', 'tariff_code', sa.text('created_at DESC')],
                    unique=False)

    # --- 2. material_conversion_formulas ---
    op.create_table(
        'material_conversion_formulas',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('material_id', sa.UUID(), nullable=False),
        sa.Column('formula_type', sa.String(length=40), nullable=False,
                  comment='battery_to_lead | drosses_to_lead | scrap_with_terminal_to_lead | custom (bloqueado F1)'),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  comment='Estructura por formula_type — ver Anexo D del doc v0.5'),
        sa.Column('willard_account_subtype', sa.String(length=16), nullable=True,
                  comment='escurrido | pinza — discriminador de FORMULA dentro de Willard Drosses (caso SEC); '
                          'NULL para materiales de formula unica'),
        sa.Column('notes', sa.String(length=500), nullable=True,
                  comment='Contexto del cambio (ej: renegociacion IPC 2026)'),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_material_conversion_formulas_organization_id',
                    'material_conversion_formulas', ['organization_id'], unique=False)
    # ix_mcf_org del doc se omite: el indice del mixin (arriba) ya cubre organization_id
    op.create_index('ix_mcf_material_current', 'material_conversion_formulas',
                    ['material_id', 'willard_account_subtype', sa.text('created_at DESC')],
                    unique=False)

    # --- 3. kg_ledger_accounts ---
    op.create_table(
        'kg_ledger_accounts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False,
                  comment='Codigo corto unico por org (WILLARD-BAT-BAQ, INTERSEDE-CV-JM, ...)'),
        sa.Column('display_name', sa.String(length=120), nullable=False),
        sa.Column('account_type', sa.String(length=32), nullable=False,
                  comment='willard_baterias | willard_drosses | intersede | intra_horno | crisol'),
        sa.Column('warehouse_id', sa.UUID(), nullable=True,
                  comment='Sub-saldo por sede (willard_baterias) o sede fisica (intra_horno/crisol); NULL = org-wide'),
        sa.Column('third_party_id', sa.UUID(), nullable=True,
                  comment='Solo cuentas Willard; NULL para internas'),
        sa.Column('tolerance_kg', sa.Numeric(precision=12, scale=4), nullable=True,
                  comment='Tolerancia (+/- kg) del bloque de discrepancias del cuadre semanal; NULL = sin alerta'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.CheckConstraint(
            "account_type NOT IN ('willard_baterias', 'willard_drosses') OR third_party_id IS NOT NULL",
            name='ck_kg_ledger_accounts_willard_tp'),
        sa.CheckConstraint(
            "account_type != 'willard_baterias' OR warehouse_id IS NOT NULL",
            name='ck_kg_ledger_accounts_willard_bat_wh'),
        sa.CheckConstraint(
            "account_type NOT IN ('intra_horno', 'crisol') "
            "OR (warehouse_id IS NOT NULL AND third_party_id IS NULL)",
            name='ck_kg_ledger_accounts_intra_wh'),
        sa.CheckConstraint(
            "account_type != 'intersede' OR third_party_id IS NULL",
            name='ck_kg_ledger_accounts_intersede_tp'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['third_party_id'], ['third_parties.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_kg_ledger_accounts_org_code'),
    )
    op.create_index('ix_kg_ledger_accounts_organization_id', 'kg_ledger_accounts',
                    ['organization_id'], unique=False)
    # NULLS NOT DISTINCT (PG15+): impide dos cuentas org-wide del mismo tipo
    # incluso con warehouse_id NULL (v0.5 §11.1.1)
    op.create_index('ix_kg_ledger_account_org_type', 'kg_ledger_accounts',
                    ['organization_id', 'account_type', 'warehouse_id'],
                    unique=True, postgresql_nulls_not_distinct=True)

    # --- 4. kg_ledger_movements ---
    op.create_table(
        'kg_ledger_movements',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('account_id', sa.UUID(), nullable=False),
        sa.Column('delta_kg', sa.Numeric(precision=14, scale=4), nullable=False,
                  comment='Firmado: positivo = acumula deuda / carga; negativo = descarga / entrega'),
        sa.Column('transaction_date', sa.DateTime(timezone=True), nullable=False,
                  comment='Fecha de negocio — BusinessDate mediodia UTC via schema (app/utils/dates.py)'),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('source_type', sa.String(length=40), nullable=False,
                  comment='postconsumo_receipt | drosses_receipt | willard_subbalance_move | intersede_* | '
                          'furnace_* | crucible_* | willard_delivery | manual_adjustment | migration_initial_load'),
        sa.Column('source_id', sa.UUID(), nullable=True,
                  comment='Referencia polimorfica al evento origen segun source_type (sin FK)'),
        sa.Column('inventory_movement_id', sa.UUID(), nullable=True,
                  comment='Poblado cuando el evento kg esta atado a un movimiento fisico'),
        sa.Column('conversion_formula_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment='Snapshot exacto de la formula aplicada al momento del evento (Anexo D)'),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='confirmed',
                  comment='confirmed | annulled (soft, patron decision #48)'),
        sa.Column('annulled_reason', sa.String(length=500), nullable=True),
        sa.Column('annulled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('annulled_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.CheckConstraint('delta_kg != 0', name='ck_kg_ledger_movements_delta_nonzero'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['account_id'], ['kg_ledger_accounts.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['inventory_movement_id'], ['inventory_movements.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['annulled_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_kg_ledger_movements_organization_id', 'kg_ledger_movements',
                    ['organization_id'], unique=False)
    op.create_index('ix_kg_movement_account_date', 'kg_ledger_movements',
                    ['account_id', sa.text('transaction_date DESC')], unique=False)
    op.create_index('ix_kg_movement_source', 'kg_ledger_movements',
                    ['source_type', 'source_id'], unique=False)
    op.create_index('ix_kg_movement_org_status', 'kg_ledger_movements',
                    ['organization_id', 'status'], unique=False)

    # --- 5. kg_ledger_reconciliation_seals ---
    op.create_table(
        'kg_ledger_reconciliation_seals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('week_ending_date', sa.Date(), nullable=False,
                  comment='Viernes de cierre de la semana'),
        sa.Column('account_id', sa.UUID(), nullable=False,
                  comment='Una fila por cuenta kg (tipicamente Willard Baterias + Drosses)'),
        sa.Column('saldos_cierre', postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  comment='Snapshot de saldo cierre + apertura + totales por tipo de movimiento'),
        sa.Column('hash_movements', sa.String(length=64), nullable=False,
                  comment='SHA-256 sobre la lista ordenada de KgLedgerMovement.id de la semana — detecta ediciones post-firma'),
        sa.Column('signed_by', sa.UUID(), nullable=False),
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['account_id'], ['kg_ledger_accounts.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['signed_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'account_id', 'week_ending_date',
                            name='uq_kg_seals_org_account_week'),
    )
    op.create_index('ix_kg_ledger_reconciliation_seals_organization_id',
                    'kg_ledger_reconciliation_seals', ['organization_id'], unique=False)

    # --- 6. discrepancy_tasks ---
    op.create_table(
        'discrepancy_tasks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('discrepancy_type', sa.String(length=40), nullable=False,
                  comment='Catalogo de valores se cierra en plan E5 (detectores)'),
        sa.Column('severity', sa.String(length=16), nullable=False,
                  comment='normal | high | critical'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='open',
                  comment='open | in_review | justified | corrected | closed'),
        sa.Column('entity_type', sa.String(length=40), nullable=True,
                  comment='Polimorfico: Transfer, MoneyMovement, InventoryMovement, ...'),
        sa.Column('entity_id', sa.UUID(), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('warehouse_id', sa.UUID(), nullable=True,
                  comment='Sede de la discrepancia'),
        sa.Column('amount_involved', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('kg_involved', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('suggested_assignee_role', sa.String(length=40), nullable=True,
                  comment='Responsable sugerido (rol, no usuario) — lo fijan los detectores de E5'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.UUID(), nullable=True),
        sa.Column('resolution_notes', sa.String(length=500), nullable=True),
        sa.Column('resolution_entity_type', sa.String(length=40), nullable=True,
                  comment='Link al ajuste generado por la resolucion (ej: InventoryAdjustment)'),
        sa.Column('resolution_entity_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_discrepancy_tasks_organization_id', 'discrepancy_tasks',
                    ['organization_id'], unique=False)
    op.create_index('ix_discrepancy_tasks_org_status', 'discrepancy_tasks',
                    ['organization_id', 'status'], unique=False)
    op.create_index('ix_discrepancy_tasks_entity', 'discrepancy_tasks',
                    ['entity_type', 'entity_id'], unique=False)

    # --- 7. daily_ok_seals ---
    op.create_table(
        'daily_ok_seals',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('sealed_date', sa.Date(), nullable=False,
                  comment='Dia de negocio sellado'),
        sa.Column('tasks_resolved_count', sa.Integer(), nullable=False),
        sa.Column('signed_by', sa.UUID(), nullable=False),
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['signed_by'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'sealed_date', name='uq_daily_ok_seals_org_date'),
    )
    op.create_index('ix_daily_ok_seals_organization_id', 'daily_ok_seals',
                    ['organization_id'], unique=False)

    # --- 8. drivers ---
    op.create_table(
        'drivers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('document_id', sa.String(length=30), nullable=True),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_drivers_organization_id', 'drivers', ['organization_id'], unique=False)

    # --- 9. vehicles (sin UNIQUE de placa en BD — D14: unicidad ACTIVA en servicio) ---
    op.create_table(
        'vehicles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('plate', sa.String(length=15), nullable=False,
                  comment='Unicidad de placa ACTIVA validada en servicio (D14) — sin UNIQUE en BD'),
        sa.Column('display_name', sa.String(length=120), nullable=True),
        sa.Column('vehicle_type', sa.String(length=16), nullable=True,
                  comment='camion | montacargas | otro'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_vehicles_organization_id', 'vehicles', ['organization_id'], unique=False)

    # --- 10. inbound_orders (FK a drivers/vehicles: van despues de esos maestros) ---
    op.create_table(
        'inbound_orders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('order_number', sa.Integer(), nullable=False,
                  comment='Consecutivo por org (patron sequential numbering del repo)'),
        sa.Column('inbound_type', sa.String(length=24), nullable=False,
                  comment='purchase | postconsumo_baterias | drosses | ruta | reventa'),
        sa.Column('warehouse_id', sa.UUID(), nullable=False,
                  comment='Sede de recepcion fisica — inmutable post-registro (v0.5 §7.2)'),
        sa.Column('third_party_id', sa.UUID(), nullable=False,
                  comment='Proveedor real (una entrada POR proveedor, v0.5 §7.3)'),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False,
                  comment='Fecha de negocio — BusinessDate mediodia UTC via schema'),
        sa.Column('driver_id', sa.UUID(), nullable=True),
        sa.Column('vehicle_id', sa.UUID(), nullable=True),
        sa.Column('willard_distribution_center', sa.String(length=24), nullable=True,
                  comment='Informativo (v0.5 §6.5)'),
        sa.Column('willard_account_subtype', sa.String(length=16), nullable=True,
                  comment='escurrido | pinza — obligatorio si el material es SEC (v0.5 §6.4)'),
        sa.Column('goes_directly_to_jm', sa.Boolean(), nullable=False, server_default=sa.text('false'),
                  comment='Drosses directo BOG->JM (v0.5 §7.3)'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='draft',
                  comment='draft | confirmed | annulled'),
        sa.Column('annulled_reason', sa.String(length=500), nullable=True),
        sa.Column('annulled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('annulled_by', sa.UUID(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['third_party_id'], ['third_parties.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['driver_id'], ['drivers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['annulled_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'order_number', name='uq_inbound_orders_org_number'),
    )
    op.create_index('ix_inbound_orders_organization_id', 'inbound_orders',
                    ['organization_id'], unique=False)

    # --- 11. inbound_order_lines ---
    op.create_table(
        'inbound_order_lines',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('inbound_order_id', sa.UUID(), nullable=False),
        sa.Column('material_id', sa.UUID(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('unit', sa.String(length=10), nullable=True,
                  comment='Snapshot de la unidad al capturar (kg | unidad)'),
        sa.Column('scale_weight_kg', sa.Numeric(precision=14, scale=4), nullable=True,
                  comment='Peso de bascula cuando la cantidad viene en otra unidad'),
        sa.Column('quality_notes', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inbound_order_id'], ['inbound_orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_inbound_order_lines_organization_id', 'inbound_order_lines',
                    ['organization_id'], unique=False)
    op.create_index('ix_inbound_order_lines_order', 'inbound_order_lines',
                    ['inbound_order_id'], unique=False)

    # --- 12/13. furnace_charges / crucible_charges (D2: dos tablas, no ProcessEvent) ---
    for table_name, ix_name in (
        ('furnace_charges', 'ix_furnace_charges_org_date'),
        ('crucible_charges', 'ix_crucible_charges_org_date'),
    ):
        op.create_table(
            table_name,
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('organization_id', sa.UUID(), nullable=False),
            sa.Column('event_type', sa.String(length=16), nullable=False,
                      comment='charge | discharge'),
            sa.Column('date', sa.DateTime(timezone=True), nullable=False,
                      comment='Fecha de negocio — BusinessDate mediodia UTC via schema'),
            sa.Column('material_id', sa.UUID(), nullable=False),
            sa.Column('quantity_kg', sa.Numeric(precision=14, scale=4), nullable=False,
                      comment='Kg fisicos del evento'),
            sa.Column('output_material_id', sa.UUID(), nullable=True,
                      comment='Solo discharge: material producido'),
            sa.Column('output_quantity_kg', sa.Numeric(precision=14, scale=4), nullable=True,
                      comment='Solo discharge: kg producidos'),
            sa.Column('batch_id', sa.UUID(), nullable=True,
                      comment='Lote — SIN FK (furnace_batches es Fase 2, D7). NULL en Fase 1'),
            sa.Column('status', sa.String(length=16), nullable=False, server_default='confirmed',
                      comment='confirmed | annulled'),
            sa.Column('annulled_reason', sa.String(length=500), nullable=True),
            sa.Column('annulled_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('annulled_by', sa.UUID(), nullable=True),
            sa.Column('created_by', sa.UUID(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('now()')),
            sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['output_material_id'], ['materials.id'], ondelete='RESTRICT'),
            sa.ForeignKeyConstraint(['annulled_by'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(f'ix_{table_name}_organization_id', table_name,
                        ['organization_id'], unique=False)
        op.create_index(ix_name, table_name, ['organization_id', 'date'], unique=False)


def downgrade() -> None:
    for table_name in ('crucible_charges', 'furnace_charges'):
        op.drop_index(f'ix_{table_name}_org_date', table_name=table_name)
        op.drop_index(f'ix_{table_name}_organization_id', table_name=table_name)
        op.drop_table(table_name)

    op.drop_index('ix_inbound_order_lines_order', table_name='inbound_order_lines')
    op.drop_index('ix_inbound_order_lines_organization_id', table_name='inbound_order_lines')
    op.drop_table('inbound_order_lines')

    op.drop_index('ix_inbound_orders_organization_id', table_name='inbound_orders')
    op.drop_table('inbound_orders')

    op.drop_index('ix_vehicles_organization_id', table_name='vehicles')
    op.drop_table('vehicles')

    op.drop_index('ix_drivers_organization_id', table_name='drivers')
    op.drop_table('drivers')

    op.drop_index('ix_daily_ok_seals_organization_id', table_name='daily_ok_seals')
    op.drop_table('daily_ok_seals')

    op.drop_index('ix_discrepancy_tasks_entity', table_name='discrepancy_tasks')
    op.drop_index('ix_discrepancy_tasks_org_status', table_name='discrepancy_tasks')
    op.drop_index('ix_discrepancy_tasks_organization_id', table_name='discrepancy_tasks')
    op.drop_table('discrepancy_tasks')

    op.drop_index('ix_kg_ledger_reconciliation_seals_organization_id',
                  table_name='kg_ledger_reconciliation_seals')
    op.drop_table('kg_ledger_reconciliation_seals')

    op.drop_index('ix_kg_movement_org_status', table_name='kg_ledger_movements')
    op.drop_index('ix_kg_movement_source', table_name='kg_ledger_movements')
    op.drop_index('ix_kg_movement_account_date', table_name='kg_ledger_movements')
    op.drop_index('ix_kg_ledger_movements_organization_id', table_name='kg_ledger_movements')
    op.drop_table('kg_ledger_movements')

    op.drop_index('ix_kg_ledger_account_org_type', table_name='kg_ledger_accounts')
    op.drop_index('ix_kg_ledger_accounts_organization_id', table_name='kg_ledger_accounts')
    op.drop_table('kg_ledger_accounts')

    op.drop_index('ix_mcf_material_current', table_name='material_conversion_formulas')
    op.drop_index('ix_material_conversion_formulas_organization_id',
                  table_name='material_conversion_formulas')
    op.drop_table('material_conversion_formulas')

    op.drop_index('ix_st_code_current', table_name='service_tariffs')
    op.drop_index('ix_service_tariffs_organization_id', table_name='service_tariffs')
    op.drop_table('service_tariffs')
