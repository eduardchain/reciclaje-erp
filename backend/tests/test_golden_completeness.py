"""Guarda de la comprobacion de corrida completa del golden.

⚠️ POR QUE ESTE ARCHIVO EXISTE. El 2026-08-18 `golden_diff.py` reporto
"RESULTADO: 0 diffs reales" comparando dos directorios **inexistentes**:
`golden_capture.py` aborta por credenciales faltantes ANTES del mkdir, y
`Path.glob` sobre un directorio que no existe devuelve vacio sin excepcion. El
gate mas caro del repo —el que decide si las 3 orgs cliente se rompen— salio
verde sin haber mirado un solo byte.

`missing`/`extra` de `golden_diff` ya comparaban por NOMBRE, que es mas fuerte
que por conteo: cualquier asimetria la cazan. Pero son guardas RELATIVAS, o sea
que comparan un lado contra el otro — con los dos lados vacios se satisfacen
vacuosamente, y con los dos **igualmente incompletos** tambien. Por eso el
arreglo no fue "comparar conteos" (ya estaba, y mejor) sino un chequeo
ABSOLUTO: el manifiesto que `golden_capture` escribe **solo si termino sin
fallas**.

Misma familia que el smoke `0 == 0` de #98, que el lint que no arrancaba de #97
y que la muestra anti-correlacionada de #96 C: el sintoma de un gate roto es que
todo sale verde.
"""
import importlib.util
import json
import pathlib

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "golden_diff.py"


def _load():
    """Importa el script sin ejecutar su main (vive bajo `if __name__`)."""
    spec = importlib.util.spec_from_file_location("_golden_diff", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _lado(d: pathlib.Path, archivos: dict, con_manifiesto: bool = True):
    """Arma un directorio como lo dejaria una corrida de golden_capture."""
    d.mkdir(parents=True, exist_ok=True)
    for nombre, payload in archivos.items():
        (d / nombre).write_text(json.dumps(payload))
    if con_manifiesto:
        (d / "_manifest.json").write_text(json.dumps(
            {"capturas": len(archivos), "archivos": sorted(archivos),
             "base_url": "http://localhost:8001"}))
    return d


CAPTURAS = {
    "costa__pnl_period.json": {"total": 100},
    "costa__warehouses.json": {"items": []},
}


class TestCorridaCompleta:
    """El chequeo absoluto: distinguir "no corrio" de "paso"."""

    def test_directorio_inexistente_aborta(self, tmp_path):
        """🔴 EL CASO REAL. Antes del fix esto imprimia "0 diffs reales"."""
        mod = _load()
        with pytest.raises(SystemExit) as exc:
            mod.exigir_corrida_completa("BEFORE", tmp_path / "no_existe")
        assert "_manifest.json" in str(exc.value)

    def test_directorio_vacio_aborta(self, tmp_path):
        """La captura alcanzo a crear el directorio y murio despues."""
        mod = _load()
        vacio = tmp_path / "vacio"
        vacio.mkdir()
        with pytest.raises(SystemExit):
            mod.exigir_corrida_completa("AFTER", vacio)

    def test_corrida_incompleta_aborta_y_nombra_lo_que_falta(self, tmp_path):
        """El caso SUTIL, que las guardas relativas no ven: un lado a medias.

        Si el otro lado quedara a medias igual, `missing`/`extra` coincidirian y
        el diff saldria verde sobre una superficie encogida.
        """
        mod = _load()
        d = _lado(tmp_path / "medias", CAPTURAS)
        (d / "costa__warehouses.json").unlink()
        with pytest.raises(SystemExit) as exc:
            mod.exigir_corrida_completa("AFTER", d)
        assert "costa__warehouses.json" in str(exc.value)

    def test_captura_de_mas_tambien_aborta(self, tmp_path):
        """Un archivo que el manifiesto no declara = mezcla de dos corridas.

        Es el modo de falla que el encabezado de golden_capture ya advierte:
        usar la copia del worktree para `before` produce otro set de archivos.
        """
        mod = _load()
        d = _lado(tmp_path / "mezcla", CAPTURAS)
        (d / "costa__tp_statement_busy.json").write_text("{}")
        with pytest.raises(SystemExit) as exc:
            mod.exigir_corrida_completa("BEFORE", d)
        assert "tp_statement_busy" in str(exc.value)

    def test_corrida_completa_pasa(self, tmp_path):
        """La no-regresion: el camino feliz sigue pasando sin ruido."""
        mod = _load()
        d = _lado(tmp_path / "ok", CAPTURAS)
        mod.exigir_corrida_completa("BEFORE", d)  # no levanta

    def test_el_manifiesto_no_se_diffea_como_captura(self, tmp_path):
        """`_manifest.json` lleva la base_url, que SIEMPRE difiere entre lados
        (:8001 vs :8002). Si entrara al diff, todo golden daria un diff real."""
        mod = _load()
        before = _lado(tmp_path / "b", CAPTURAS)
        after = _lado(tmp_path / "a", CAPTURAS)
        (after / "_manifest.json").write_text(json.dumps(
            {"capturas": 2, "archivos": sorted(CAPTURAS),
             "base_url": "http://localhost:8002"}))
        import sys
        argv = sys.argv
        sys.argv = ["golden_diff", str(before), str(after)]
        try:
            with pytest.raises(SystemExit) as exc:
                mod.main()
            assert exc.value.code == 0, "el manifiesto se colo al diff"
        finally:
            sys.argv = argv
