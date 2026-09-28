Saca la validación de inventario de las ventas del Punto de Venta fuera de la petición del cajero y
la procesa en una **cola persistente**, un picking a la vez por producto. Así varias cajas pueden
vender el mismo producto al mismo tiempo sin chocar en la base de datos.

Sin el módulo, con inventario **en tiempo real**, cada venta valida su picking (`_action_done()`)
dentro de la misma petición que registra la orden. Cuando dos cajas tocan el mismo producto a la
vez, PostgreSQL devuelve errores de serialización o de bloqueo; además, el core de Odoo atrapa los
`UserError`/`ValidationError` de esa validación y los descarta en silencio, y el picking queda sin
validar.

Con el módulo, la venta solo **crea** el picking y deja un ítem `pending` en la cola, en la misma
transacción de la orden. El worker de cron valida después cada picking, con bloqueos por producto y
compañía, reintentos y registro del error si falla. Los fallos quedan a la vista en
*Punto de venta › Órdenes › Cola de Inventario*, y la sesión no se puede cerrar mientras quede
inventario sin validar.

La cola se enciende y apaga con un **interruptor global**, activado por defecto.
