"""Costo de envío de un pedido."""
from tienda.config import ENVIO_GRATIS_DESDE, TARIFAS_POR_CIUDAD, TARIFA_NACIONAL


def costo_envio(pedido):
    subtotal = sum(item["precio"] * item["cantidad"] for item in pedido["items"])
    if subtotal > ENVIO_GRATIS_DESDE:
        return 0
    return TARIFAS_POR_CIUDAD.get(pedido["ciudad"], TARIFA_NACIONAL)


def cambiar_ciudad(pedido, ciudad):
    pedido["ciudad"] = ciudad
    pedido["envio"] = TARIFAS_POR_CIUDAD.get(ciudad, TARIFA_NACIONAL)
    pedido["total"] = pedido["subtotal"] + pedido["envio"] - pedido.get("descuento", 0)
    return pedido


def generar_guia(pedido, transportadora):
    if not pedido.get("pagado"):
        raise ValueError("No se genera guía para pedidos sin pago confirmado")
    return {"pedido": pedido["id"], "transportadora": transportadora, "ciudad": pedido["ciudad"]}
