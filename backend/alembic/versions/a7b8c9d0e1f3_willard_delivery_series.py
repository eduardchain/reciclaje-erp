"""willard_deliveries.series — consecutivo por serie: Venta #n / Abono #n (#105 D1)

Hugo, 28-ago: "para los abonos tenemos un consecutivo y para la venta otro
consecutivo [...] que es el que llevo con Willard". Hasta aqui `delivery_number`
era un solo contador para los tres tipos.

La serie es columna NOT NULL con un CHECK que codifica el mapping tipo->serie
(una fila con un tipo sin serie declarada NO puede insertarse: fail-closed) y la
unicidad pasa de (org, numero) a (org, serie, numero). El texto del CHECK es el
mismo que genera `series_check_sql()` en el modelo; `schema_parity_check.py` los
compara.

CONGELA los numeros existentes (F3 de QA; Daniel: "irrelevante, son datos de
prueba" -> se toma el camino que no reescribe nada): la columna se llena desde
el tipo y ningun `delivery_number` cambia; cada serie arranca en su maximo. Con
el unico global viejo los numeros ya eran unicos dentro de cada serie, asi que
el indice nuevo se crea sin conflicto por construccion.

Tabla exclusiva SAC (router tras `require_org_flag("kg_ledger_enabled")`): cero
filas en las 3 orgs cliente.

Revision ID: a7b8c9d0e1f3
Revises: f0a1b2c3d4e5
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f3"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None

# Congelado: igual a `series_check_sql()` del modelo al momento de esta migracion.
SERIES_CHECK = (
    "(delivery_type IN ('venta') AND series = 'venta') OR "
    "(delivery_type IN ('abono_bateria', 'abono_material') AND series = 'abono')"
)


def upgrade() -> None:
    op.add_column(
        "willard_deliveries",
        sa.Column(
            "series",
            sa.String(10),
            nullable=True,
            comment="Serie del consecutivo (#105 D1): venta | abono. Derivada del tipo; la BD la exige",
        ),
    )
    conn = op.get_bind()
    # El backfill usa un CASE fijo (`ELSE 'abono'`) y no el mapping del modelo a
    # proposito: una migracion es una foto congelada, y el CHECK que se crea justo
    # despues rechaza cualquier tipo fuera del mapping — si aqui entrara un tipo
    # desconocido como 'abono', el CHECK lo tumbaria en esta misma migracion.
    n = conn.execute(
        sa.text(
            "UPDATE willard_deliveries SET series = "
            "CASE WHEN delivery_type = 'venta' THEN 'venta' ELSE 'abono' END "
            "WHERE series IS NULL"
        )
    ).rowcount
    print(f"[a7b8c9d0e1f3] series llenada desde el tipo en {n} salida(s); numeros intactos")
    op.alter_column("willard_deliveries", "series", nullable=False)
    op.create_check_constraint(
        "ck_willard_delivery_series", "willard_deliveries", SERIES_CHECK
    )
    op.drop_constraint("uq_willard_delivery_number", "willard_deliveries", type_="unique")
    op.create_unique_constraint(
        "uq_willard_delivery_series_number",
        "willard_deliveries",
        ["organization_id", "series", "delivery_number"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    # Volver al unico global solo es posible si ninguna venta y abono creados
    # DESPUES de la migracion comparten numero. Si comparten, se renumera por
    # instante de creacion — LOSSY (los numeros originales no se recuperan),
    # declarado en el plan.
    dups = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM (SELECT organization_id, delivery_number "
            "FROM willard_deliveries GROUP BY 1, 2 HAVING COUNT(*) > 1) d"
        )
    ).scalar()
    if dups:
        n = conn.execute(
            sa.text(
                "WITH ranked AS ("
                "  SELECT id, ROW_NUMBER() OVER ("
                "    PARTITION BY organization_id ORDER BY created_at, delivery_number"
                "  ) AS n FROM willard_deliveries"
                ") UPDATE willard_deliveries d SET delivery_number = r.n "
                "FROM ranked r WHERE r.id = d.id"
            )
        ).rowcount
        print(
            f"[a7b8c9d0e1f3] downgrade: {dups} colision(es) entre series -> "
            f"renumeradas {n} salidas por created_at (LOSSY)"
        )
    op.drop_constraint(
        "uq_willard_delivery_series_number", "willard_deliveries", type_="unique"
    )
    op.create_unique_constraint(
        "uq_willard_delivery_number",
        "willard_deliveries",
        ["organization_id", "delivery_number"],
    )
    op.drop_constraint("ck_willard_delivery_series", "willard_deliveries", type_="check")
    op.drop_column("willard_deliveries", "series")
