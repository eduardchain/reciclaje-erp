"""Guarda del normalizador de CHECKs del parity check.

`schema_parity_check.py` compara el esquema migrado (dev) contra el que produce
`create_all` (test). Postgres renderiza el MISMO CHECK de dos formas segun como
se creo —castea cada elemento del array, o castea el array entero— asi que el
comparador normaliza el texto antes de comparar.

⚠️ POR QUE ESTE ARCHIVO EXISTE. El riesgo no es la regex de hoy: es la que
alguien ensanche mañana. Un comparador que normaliza de mas convierte el gate en
decorado —diria DIFF CERO con una divergencia real encima— y nadie se enteraria,
porque el sintoma de un gate roto es que todo sale verde.

Es exactamente la forma que ya mordio en #92: el patron
`datetime\\.now\\([^)]*\\)\\.date\\(\\)` no cruzaba el parentesis interno y
escondia 6 sitios. La respuesta correcta fue hacer que la guarda se pruebe a si
misma, y eso es lo que se calca aca.
"""
import importlib.util
import pathlib

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "schema_parity_check.py"


def _load_normalizer():
    """Importa el script sin ejecutar su main (vive bajo `if __name__`)."""
    spec = importlib.util.spec_from_file_location("_parity_check", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.normalize_condef


# Las dos formas del MISMO check, tal como las devuelve pg_get_constraintdef.
# Copiadas literales de una corrida real contra material_kg_profiles.
DEV = (
    "CHECK (((willard_world)::text = ANY (ARRAY[('none'::character varying)::text, "
    "('postconsumo'::character varying)::text, ('drosses'::character varying)::text])))"
)
TEST = (
    "CHECK (((willard_world)::text = ANY ((ARRAY['none'::character varying, "
    "'postconsumo'::character varying, 'drosses'::character varying])::text[])))"
)


class TestParityNormalizer:
    """El normalizador colapsa las formas equivalentes y NADA mas."""

    def test_colapsa_las_dos_formas_del_mismo_check(self):
        n = _load_normalizer()
        assert n(DEV) == n(TEST), (
            "El normalizador dejo de reconocer las dos formas de castear el mismo "
            "array — el parity check volveria a salir rojo por cosmetica"
        )

    @pytest.mark.parametrize(
        "descripcion,alterado",
        [
            (
                "un valor distinto en la lista",
                TEST.replace("drosses", "OTRO_MUNDO"),
            ),
            (
                "un valor de MENOS en la lista",
                TEST.replace("'drosses'::character varying", "").replace(", ]", "]"),
            ),
            (
                "una columna distinta",
                TEST.replace("willard_world", "otra_columna"),
            ),
        ],
    )
    def test_una_diferencia_real_sigue_reportando(self, descripcion, alterado):
        """Lo que la guarda protege de verdad: que ensanchar la regex no empiece
        a esconder divergencias semanticas."""
        n = _load_normalizer()
        assert n(DEV) != n(alterado), (
            f"El normalizador esta escondiendo {descripcion}: el gate diria "
            "DIFF CERO con una divergencia real encima"
        )

    @pytest.mark.parametrize(
        "izq,der",
        [
            # Operador distinto sobre el mismo campo
            ("CHECK ((amount > (0)::numeric))", "CHECK ((amount >= (0)::numeric))"),
            # Nullable-guard invertido
            ("CHECK ((warehouse_id IS NOT NULL))", "CHECK ((warehouse_id IS NULL))"),
            # ANY vs ALL — la diferencia entre "esta en la lista" y "no esta"
            (
                "CHECK (((t)::text = ANY (ARRAY[('a'::character varying)::text])))",
                "CHECK (((t)::text <> ALL (ARRAY[('a'::character varying)::text])))",
            ),
        ],
    )
    def test_no_toca_la_semantica(self, izq, der):
        n = _load_normalizer()
        assert n(izq) != n(der)

    def test_solo_quita_casts_redundantes(self):
        """Un CHECK sin arrays casteados pasa intacto: la normalizacion es
        estrecha, no una limpieza general del texto."""
        n = _load_normalizer()
        plano = "CHECK ((delta_kg <> (0)::numeric))"
        assert n(plano) == plano

    def test_none_no_revienta(self):
        """`diff_section` la llama con el lado ausente cuando un CHECK existe en
        una sola punta."""
        n = _load_normalizer()
        assert n(None) is None
