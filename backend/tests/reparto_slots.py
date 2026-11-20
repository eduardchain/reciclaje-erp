"""Slots por defecto para los tests que NO prueban slots (plan reparto por
compra, A5).

Desde el reparto por compra cada asignacion lleva `purchase_slot` (la compra
de la Entrada a la que va). Los tests escritos antes asumen «una compra por
proveedor», asi que este helper les pone el slot de su proveedor en orden de
primera aparicion: el primer proveedor del payload es la compra 1, el segundo
la 2… Con eso el significado de esos tests no cambia.

Los bloques por compra (retenciones, contado, IVA) que no traen slot toman el
de su proveedor; si el proveedor no esta en el reparto se les da un slot que
no existe, para que el servidor siga diciendo «no esta en el reparto».

Un test que SI prueba slots (`test_sac_reparto_por_compra.py`) los pone a mano
y no pasa por aca. Un payload que ya trae `purchase_slot` se respeta.
"""
import copy


def con_slots(payload):
    if not isinstance(payload, dict):
        return payload
    body = copy.deepcopy(payload)
    slot_of: dict = {}

    def slot_for(tp_id):
        if tp_id not in slot_of:
            slot_of[tp_id] = len(slot_of) + 1
        return slot_of[tp_id]

    for line in body.get("lines") or []:
        if not isinstance(line, dict):
            continue
        for alloc in line.get("allocations") or []:
            if isinstance(alloc, dict) and "purchase_slot" not in alloc:
                alloc["purchase_slot"] = slot_for(alloc.get("third_party_id"))

    ghost = len(slot_of) + 100
    for key in ("supplier_retentions", "supplier_payments", "purchase_taxes"):
        for block in body.get(key) or []:
            if isinstance(block, dict) and "purchase_slot" not in block:
                tp_id = block.get("third_party_id")
                if tp_id in slot_of:
                    block["purchase_slot"] = slot_of[tp_id]
                else:
                    block["purchase_slot"] = ghost
                    ghost += 1
    return body
