"""Tipo compartido de la remision (talonario de remisiones de SAC, Q-75).

La remision sale del MISMO talonario de las Entradas: obligatoria, con strip
ANTES de min_length («  » no pasa: min_length solo cuenta caracteres, leccion de
#100). Lo usan la Salida de control y el traslado.

`schemas/willard_delivery.py` tiene su propia copia inline de las mismas
restricciones y NO se toca (Salidas de Plomo esta fuera del talonario); si
cambian las restricciones, se cambian en los dos sitios.
"""
from typing import Annotated

from pydantic import StringConstraints

RemissionStr = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]
