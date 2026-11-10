"""Aplicación de cupones de descuento al carrito."""
from datetime import date

from tienda.config import CUPON_MAXIMO_PORCENTAJE


def aplicar_cupon(carrito, cupon, hoy=None):
    hoy = hoy or date.today()
    if not cupon["activo"] or hoy > cupon["vence"]:
        return 0
    # Los productos en oferta no acumulan descuento.
    if any(item.get("en_oferta") for item in carrito["items"]):
        return 0
    base = sum(item["precio"] * item["cantidad"] for item in carrito["items"])
    porcentaje = min(cupon["porcentaje"], CUPON_MAXIMO_PORCENTAJE)
    return round(base * porcentaje / 100)
