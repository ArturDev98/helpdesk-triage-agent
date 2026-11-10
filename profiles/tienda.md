# @NOMBRE
Tienda Demo

# @DOMINIO
Tienda en línea ficticia: catálogo, carrito, cupones de descuento, pagos con tarjeta y PSE, envíos a
domicilio con envío gratis desde un monto mínimo, e inventario por bodega. Los usuarios de la mesa son
el equipo de servicio al cliente y los administradores de la tienda.

# @MODULOS
- cupones: reglas de descuento, vigencia, compatibilidad con productos en oferta.
- pagos: tarjeta, PSE, reintentos y conciliación.
- envios: costo, envío gratis, transportadoras y guías.
- inventario: existencias por bodega, reservas del carrito.
- cuentas: registro, inicio de sesión, recuperación de contraseña.

# @REGLAS
- El código del demo está en `demo/codebase/tienda/`; la configuración, en `config/`.
- Los montos se manejan en pesos sin decimales.
- Un pedido con envío gratis no debe cobrar transporte aunque cambie la ciudad.
