"""Pagos con tarjeta y PSE."""
from tienda import inventario


def registrar_respuesta_pasarela(pedido, respuesta):
    estado = respuesta["estado"]
    if estado == "APROBADO":
        pedido["pagado"] = True
        inventario.confirmar_pago(pedido["id"], aprobado=True)
    elif estado == "RECHAZADO":
        pedido["pagado"] = False
        inventario.confirmar_pago(pedido["id"], aprobado=False)
    else:
        # PSE puede quedar PENDIENTE; la conciliación de cada hora lo resuelve.
        pedido["estado_pago"] = "PENDIENTE"
    return pedido
