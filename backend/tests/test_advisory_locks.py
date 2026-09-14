"""Advisory locks de numeracion: llave estable, generador unico, orden canonico.

Plan: `docs/planes/plan-advisory-locks-estables.md`. Tres defectos cerrados:
  A. la llave salia de `hash()`, aleatorizado POR PROCESO — con `--workers 4`
     en produccion, dos workers serializaban sobre llaves distintas;
  B. `purchase_number`/`sale_number` tenian dos generadores con dos llaves;
  C. flujos que toman varios locks en orden cruzado → deadlock posible.

⚠️ SOBRE LA VERIFICACION. Dentro de UN proceso `hash()` es determinista, asi
que "dos llamadas dan lo mismo" no prueba nada: T1 lanza subprocesos con
semillas distintas. Y "el hilo no termino a los 0,5 s" tampoco prueba que
espera (puede no haber arrancado): T4 exige ver al backend de la sesion B en
`pg_stat_activity` con `wait_event='advisory'` — evidencia positiva (F2 de QA).
"""
import os
import pathlib
import re
import subprocess
import sys
import threading
import time
import zlib
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text

from app.models.organization import Organization
from app.utils import advisory_locks as al
from app.utils.advisory_locks import (
    RANK,
    SEQUENCES,
    LockOrderError,
    lock_sequence,
    lock_sequences,
    next_number,
    sequence_lock_key,
)
from tests.conftest import TestingSessionLocal, test_engine

BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_DIR / "app"
HELPER = APP_DIR / "utils" / "advisory_locks.py"


# ---------------------------------------------------------------------------
# T1 — la llave es la misma en procesos con semillas distintas; hash() no
# ---------------------------------------------------------------------------
_SNIPPET = (
    "import sys, uuid\n"
    "from app.utils.advisory_locks import sequence_lock_key\n"
    "org = uuid.UUID(sys.argv[1])\n"
    "print(sequence_lock_key(org, 'purchase_number'), hash(str(org)))\n"
)


def _en_otro_proceso(seed: int, org) -> tuple[int, int]:
    env = {**os.environ, "PYTHONHASHSEED": str(seed)}
    out = subprocess.run(
        [sys.executable, "-c", _SNIPPET, str(org)],
        env=env, cwd=BACKEND_DIR, capture_output=True, text=True, check=True,
    ).stdout.split()
    return int(out[0]), int(out[1])


class TestLlave:
    def test_llave_estable_entre_procesos(self):
        """T1 (P4): tres procesos con PYTHONHASHSEED distinto. El helper da la
        MISMA llave en los tres; `hash(str(org))` no — que es exactamente lo que
        pasaba entre los 4 workers de produccion."""
        org = uuid4()
        resultados = [_en_otro_proceso(seed, org) for seed in (1, 2, 3)]
        llaves = {k for k, _ in resultados}
        hashes = {h for _, h in resultados}
        assert llaves == {sequence_lock_key(org, "purchase_number")}
        assert len(hashes) > 1, "hash() dio lo mismo en 3 semillas: el defecto no se reproduce"

    def test_secuencias_conocidas_distintas_y_fail_closed(self):
        """T2 (P3): una llave por contador, por org y por particion; un nombre
        fuera del registro es error, no un lock nuevo inventado."""
        org, otra = uuid4(), uuid4()
        llaves = {seq: sequence_lock_key(org, seq) for seq in SEQUENCES}
        assert len(set(llaves.values())) == len(SEQUENCES)
        assert sequence_lock_key(otra, "purchase_number") != llaves["purchase_number"]
        assert (
            sequence_lock_key(org, "willard_delivery", "venta")
            != sequence_lock_key(org, "willard_delivery", "abono")
        )
        assert set(RANK) == set(SEQUENCES)
        with pytest.raises(ValueError, match="Secuencia desconocida"):
            sequence_lock_key(org, "invoice_number")
        with pytest.raises(ValueError, match="Secuencia desconocida"):
            lock_sequences(None, org, "purchase_number", "lo_que_sea")
        # next_number valida la particion ANTES de tocar la BD (db=None)
        with pytest.raises(ValueError, match="falta la particion"):
            next_number(None, org, "willard_delivery")
        with pytest.raises(ValueError, match="no tiene particion"):
            next_number(None, org, "purchase_number", "venta")

    def test_particion_willard_conserva_la_llave_de_105(self):
        """T8 (P4): la cadena es exactamente la que #105 estreno."""
        from app.services.willard_delivery import WillardDeliveryService

        org = uuid4()
        esperado = zlib.crc32(f"{org}:willard_delivery:venta".encode("utf-8"))
        assert sequence_lock_key(org, "willard_delivery", "venta") == esperado
        assert WillardDeliveryService._lock_key(org, "venta") == esperado


# ---------------------------------------------------------------------------
# T3 — guarda: nada de esto vive fuera del helper (inventario permitido: vacio)
# ---------------------------------------------------------------------------
_PROHIBIDO = [
    ("pg_advisory", re.compile(r"pg_advisory")),
    ("llave con hash()", re.compile(r"lock_id\s*=\s*hash\(")),
    ("MAX de un consecutivo", re.compile(r"func\.max\(\w+\.\w*_number\)|MAX\(\w*_number\)")),
]


class TestGuarda:
    def test_ningun_lock_ni_contador_fuera_del_helper(self):
        """T3 (P1, P2): el dia que alguien copie un generador "por comodidad"
        con su propio lock o su propio MAX, esto lo nombra. Es el patron de
        `RELOJES_PERMITIDOS` con el inventario permitido VACIO."""
        ofensores = []
        for path in sorted(APP_DIR.rglob("*.py")):
            if path == HELPER:
                continue
            for n, line in enumerate(path.read_text().splitlines(), 1):
                for etiqueta, pat in _PROHIBIDO:
                    if pat.search(line):
                        ofensores.append(f"{path.relative_to(BACKEND_DIR)}:{n} [{etiqueta}] {line.strip()}")
        assert not ofensores, "Numeracion fuera del helper:\n  " + "\n  ".join(ofensores)


# ---------------------------------------------------------------------------
# T4 — dos sesiones (como dos workers) se esperan sobre el mismo contador
# ---------------------------------------------------------------------------
def _wait_event(probe, pid):
    """Snapshot FRESCO de pg_stat_activity (dentro de una transaccion la vista
    se congela; el rollback la libera)."""
    row = probe.execute(
        text("SELECT wait_event_type, wait_event FROM pg_stat_activity WHERE pid = :pid"),
        {"pid": pid},
    ).first()
    probe.rollback()
    return (row[0], row[1]) if row else None


class TestBloqueo:
    def test_dos_sesiones_esperan_el_mismo_lock(self, db_session):
        """T4 (P4, defecto A): la sesion A retiene `purchase_number`; la sesion
        B (otra conexion, como otro worker) pide el siguiente numero y tiene
        que quedarse en espera 'advisory' — visto en pg_stat_activity, no
        inferido de un sleep — hasta que A suelta."""
        org = uuid4()
        a, b, probe = TestingSessionLocal(), TestingSessionLocal(), TestingSessionLocal()
        estado: dict = {}

        def worker():
            estado["pid"] = b.execute(text("SELECT pg_backend_pid()")).scalar_one()
            estado["numero"] = next_number(b, org, "purchase_number")

        t = threading.Thread(target=worker, daemon=True)
        try:
            lock_sequence(a, org, "purchase_number")  # A retiene; tx abierta
            t.start()
            visto = None
            limite = time.monotonic() + 5
            while time.monotonic() < limite:
                pid = estado.get("pid")
                if pid is not None:
                    visto = _wait_event(probe, pid)
                    if visto == ("Lock", "advisory"):
                        break
                time.sleep(0.05)
            assert visto == ("Lock", "advisory"), (
                f"B nunca entro en espera 'advisory' (ultimo estado: {visto}); "
                "con llaves distintas por sesion B no espera a nadie"
            )
            assert "numero" not in estado, "B calculo el numero con A reteniendo el lock"
            a.rollback()  # suelta
            t.join(5)
            assert not t.is_alive() and estado["numero"] == 1
        finally:
            a.rollback()
            a.close()
            t.join(5)
            b.close()
            probe.close()


# ---------------------------------------------------------------------------
# T6 — cada envoltorio pide SU contador (y todos los contadores tienen uno)
# ---------------------------------------------------------------------------
class TestMapa:
    def test_cada_generador_pide_su_secuencia(self, db_session):
        """T6 (P2, P6, P7): se registra que secuencia pide cada generador de
        los servicios. Un typo que le diera a un contador dos nombres — el
        defecto B — cae aqui; un nombre fuera del registro, en T2."""
        from app.services.double_entry import double_entry
        from app.services.inbound_order import inbound_order_service
        from app.services.inventory_adjustment import inventory_adjustment
        from app.services.material_transformation import material_transformation
        from app.services.money_movement import money_movement
        from app.services.purchase import purchase
        from app.services.sale import crud_sale
        from app.services.transfer import transfer_service
        from app.services.willard_delivery import willard_delivery
        from app.services.crucible_charge import crucible_charge_service

        casos = [
            (purchase._generate_purchase_number, ("purchase_number", None)),
            (crud_sale._generate_sale_number, ("sale_number", None)),
            (double_entry._generate_double_entry_number, ("double_entry_number", None)),
            (money_movement._generate_movement_number, ("movement_number", None)),
            (inventory_adjustment._generate_adjustment_number, ("adjustment_number", None)),
            (material_transformation._generate_transformation_number, ("transformation_number", None)),
            (transfer_service._generate_transfer_number, ("transfer_number", None)),
            (inbound_order_service._generate_order_number, ("inbound_order_number", None)),
            # #107 (T15): el documento de crisol numera con su propia secuencia
            (crucible_charge_service._generate_charge_number, ("crucible_number", None)),
            (lambda db, org: willard_delivery._next_number(db, org, "venta"), ("willard_delivery", "venta")),
        ]
        org = uuid4()
        vistos = []
        real = al.sequence_lock_key

        def grabar(organization_id, sequence, partition=None):
            vistos.append((sequence, partition))
            return real(organization_id, sequence, partition)

        s = TestingSessionLocal()
        try:
            with patch.object(al, "sequence_lock_key", side_effect=grabar):
                for gen, esperado in casos:
                    vistos.clear()
                    assert gen(s, org) == 1  # tablas vacias: el primero es 1
                    assert vistos == [esperado], f"{esperado[0]}: pidio {vistos}"
                    s.rollback()  # suelta el lock y limpia el orden entre casos
        finally:
            s.close()
        assert {e[0] for _, e in casos} == set(SEQUENCES), "todo contador tiene su generador"


# ---------------------------------------------------------------------------
# T7 — la red de doble partida existe en el esquema que nace de los modelos
# ---------------------------------------------------------------------------
class TestUnicidadDoblePartida:
    def test_constraint_en_el_esquema(self, db_session):
        """T7a (P5): `uq_double_entries_org_number` esta en el modelo (el 5433
        nace de los modelos). La migracion se verifica en dev con psql."""
        uqs = inspect(test_engine).get_unique_constraints("double_entries")
        assert any(
            set(u["column_names"]) == {"organization_id", "double_entry_number"} for u in uqs
        ), uqs


# ---------------------------------------------------------------------------
# T9 — el orden canonico se EXIGE
# ---------------------------------------------------------------------------
class TestOrdenCanonico:
    def test_orden_canonico_se_exige(self, db_session):
        """T9 (P9): rango menor al maximo retenido → LockOrderError; re-adquirir
        nunca levanta (Entrada: movement → adjustment → movement); el registro
        muere con la transaccion raiz (rollback Y close) pero NO con un flush
        (subtransaccion, C2 de QA); y `lock_sequences` ordena por rango ANTES
        de adquirir, reciba la tupla como la reciba."""
        org = uuid4()
        s = TestingSessionLocal()
        try:
            lock_sequence(s, org, "movement_number")
            lock_sequence(s, org, "adjustment_number")
            # C2 (QA): un flush con algo pendiente abre una SUBtransaccion y el
            # listener solo limpia en la raiz (`transaction.parent is None`). Si
            # alguien "simplifica" esa condicion, D4b queda vacuo en todo flujo
            # real (todos flushean entre locks) y ningun test positivo lo nota.
            s.add(Organization(name="org-locks-flush", slug=f"locks-flush-{uuid4().hex[:8]}"))
            s.flush()
            assert al._held(s) == {"movement_number", "adjustment_number"}, (
                "el flush (subtransaccion) borro el registro de locks"
            )
            with pytest.raises(LockOrderError, match="purchase_number"):
                lock_sequence(s, org, "purchase_number")
            lock_sequence(s, org, "movement_number")  # re-adquirir: valido
            assert al._held(s) == {"movement_number", "adjustment_number"}

            s.rollback()
            assert s.info.get(al._HELD_KEY) is None, "el rollback no limpio el registro"
            lock_sequence(s, org, "adjustment_number")
            with pytest.raises(LockOrderError):
                lock_sequence(s, org, "movement_number")  # orden evaluado de cero
            s.rollback()

            lock_sequence(s, org, "adjustment_number")
            s.close()  # con transaccion abierta
            assert s.info.get(al._HELD_KEY) is None, "el close no limpio el registro"

            orden = []
            with patch.object(al, "lock_sequence", side_effect=lambda db, o, seq, partition=None: orden.append(seq)):
                lock_sequences(s, org, "adjustment_number", "movement_number", "purchase_number")
            assert orden == ["purchase_number", "movement_number", "adjustment_number"]

            # y de verdad, contra PG, la tupla desordenada no levanta
            lock_sequences(s, org, "adjustment_number", "movement_number")
            assert al._held(s) == {"movement_number", "adjustment_number"}
            lock_sequence(s, org, "adjustment_number")  # re-entrante tras la declaracion
            s.rollback()
        finally:
            s.close()


class TestCrisol:
    """#107 T15 — el documento de crisol entra al catalogo con su rango."""

    def test_crucible_number_en_el_mapa_con_rango_14(self):
        from app.utils.advisory_locks import RANK, SEQUENCES

        assert SEQUENCES["crucible_number"] == ("crucible_charges", "charge_number", None)
        assert RANK["crucible_number"] == 14
        assert RANK["willard_delivery"] == 13
        assert RANK["crucible_number"] < RANK["movement_number"]
        # F2 de QA: dos secuencias con el mismo rango se podrian tomar en
        # cualquier orden y el orden canonico dejaria de ser total.
        assert len(set(RANK.values())) == len(RANK)

    def test_dross_return_pide_crisol_y_despues_movimiento(self, db_session, test_organization):
        """El retorno de dross numera el documento (14) y despues el par (30):
        declarado anticipado, y el orden inverso revienta."""
        from app.utils.advisory_locks import LockOrderError, lock_sequence, lock_sequences

        org = test_organization.id
        lock_sequences(db_session, org, "crucible_number", "movement_number")
        db_session.rollback()

        lock_sequence(db_session, org, "movement_number")
        with pytest.raises(LockOrderError):
            lock_sequence(db_session, org, "crucible_number")
        db_session.rollback()
