"""Existencias por bodega y reservas del carrito."""
from datetime import datetime, timedelta

from tienda.config import RESERVA_MINUTOS

reservas = {}


def disponible(producto, bodegas):
    reservado = sum(r["cantidad"] for r in reservas.values() if r["producto"] == producto["id"])
    return sum(b["unidades"].get(producto["id"], 0) for b in bodegas) - reservado


def reservar(pedido_id, producto_id, cantidad):
    reservas[pedido_id] = {"producto": producto_id, "cantidad": cantidad,
                           "vence": datetime.now() + timedelta(minutes=RESERVA_MINUTOS)}


def confirmar_pago(pedido_id, aprobado):
    if aprobado:
        reservas.pop(pedido_id, None)
    # Si el pago es rechazado la reserva queda hasta que alguien la limpie.


def limpiar_vencidas(ahora=None):
    ahora = ahora or datetime.now()
    for pedido_id in [p for p, r in reservas.items() if r["vence"] < ahora]:
        del reservas[pedido_id]
