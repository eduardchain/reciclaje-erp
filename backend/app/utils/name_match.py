"""Aviso de proveedor parecido por contenido (plan-sac-similar-por-contenido
v1.1, D1). UNA sola regla, pura y sin BD, que usa `third_party.find_similar`.

La especificación es la función medida `c_final` de `medir_criterio.py`
(evidencia del plan, 383 terceros de SAC y 484 de Costa). El gate C2 de QA la
compara par por par contra esta. Si se toca la lista de palabras vacías o el
umbral, hay que volver a medir: no es un ajuste cosmético.

Orden de decisión:
  1. exact  — `normalize_entity_name` igual (lo de hoy; la pantalla BLOQUEA).
  2. similar, regla A — la CONCATENACIÓN de las palabras significativas es
     igual: «GreenLoop» = «Green Loop», «Aluica S.A.S» = «Aluica».
  3. similar, camino C — la concatenación CRUDA (sin quitar vacías) es igual:
     «Dela Rosa» = «de la Rosa», que A no ve.
  4. similar, regla B — el CONJUNTO de significativas distintas de un nombre
     está contenido en el del otro (en cualquier dirección) y el lado
     contenido tiene >= 2 palabras o >= 8 letras: el umbral es el freno a los
     nombres cortos («ana», «green» no avisan).
Lo «similar» solo avisa (O1 de Daniel, 20-nov): la pantalla deja crear igual.

⚠️ No es el buscador de los selectores (`utils/searchMatch.ts`, #123): ese
contesta «qué nombre contiene lo que voy escribiendo», en una dirección. Acá
el nombre nuevo suele ser el MÁS LARGO, y la pregunta es simétrica.
"""
import re
from typing import Literal, Optional

from app.services.retention_entities import normalize_entity_name

MatchKind = Literal["exact", "similar"]

STOPWORDS = frozenset({
    "sas", "s", "a", "sa", "ltda", "de", "la", "el", "los", "las", "y", "e",
    "del", "cia", "co", "inc", "srl", "eu",
})
MIN_CONTAINED_WORDS = 2
MIN_CONTAINED_LETTERS = 8

_SPLIT = re.compile(r"[^a-z0-9]+")


def _words(name: str) -> list[str]:
    return [w for w in _SPLIT.split(normalize_entity_name(name)) if w]


def _significant(name: str) -> list[str]:
    return [w for w in _words(name) if w not in STOPWORDS]


def name_match_kind(new: str, old: str) -> Optional[MatchKind]:
    """`exact`, `similar` o None entre dos nombres. Simétrica."""
    if normalize_entity_name(new) == normalize_entity_name(old):
        return "exact"
    sig_new, sig_old = _significant(new), _significant(old)
    joined_new, joined_old = "".join(sig_new), "".join(sig_old)
    if joined_new and joined_new == joined_old:
        return "similar"  # regla A
    raw_new, raw_old = "".join(_words(new)), "".join(_words(old))
    if raw_new and raw_new == raw_old:
        return "similar"  # camino C
    a, b = set(sig_new), set(sig_old)
    if not a or not b:
        return None
    for small, big in ((a, b), (b, a)):
        if small <= big and (
            len(small) >= MIN_CONTAINED_WORDS
            or len("".join(small)) >= MIN_CONTAINED_LETTERS
        ):
            return "similar"  # regla B
    return None
