Avisa por correo al proveedor y a los solicitantes de compra cada vez que se registra un pago, y
deja a la vista quién pidió lo que se está pagando. Al confirmar el pago de una factura de
proveedor envía un correo al proveedor con el detalle de las facturas cubiertas, y otro a los
contactos que se hayan indicado en la orden de compra relacionada.

Para eso agrega tres cosas: el campo *Notificar pago a* (`notify_requester_ids`) en la orden de
compra, con el listado de correos calculado al lado; el campo *Solicitantes de Compra*
(`buyers_invoice_ids`) en la factura de proveedor, que muestra los usuarios que crearon las órdenes
de compra que se están facturando; y la trazabilidad del aviso en el pago, con la marca
*Notificación por correo* —visible también como columna en la lista de pagos a proveedor— y un
botón *Notificar Proveedor* para reenviarlo. El módulo está marcado como `auto_install`: se instala
solo cuando ya están instalados `account`, `purchase` y `contacts`.
