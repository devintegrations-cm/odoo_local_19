La casilla está en el formulario del método de pago:

![Casilla Ask for approval number en el método de pago del POS](../static/description/01_configuracion.png)

En la pantalla de pago, al elegir el método configurado, el POS pide el número
de aprobación. Se escribe el voucher del datáfono y se confirma con **«Apply»**:

![Diálogo del POS pidiendo el número de aprobación](../static/description/02_pos_dialogo.png)

El número aparece entre corchetes junto al importe, tanto en la línea
seleccionada como en las demás. Un pedido puede tener varias líneas del mismo
método, cada una con su propio voucher:

![Líneas de pago del POS mostrando el número de voucher junto al importe](../static/description/03_pos_lineas.png)

Una vez validado el pedido, el número se consulta en *Punto de Venta >
Pedidos*, pestaña **«Payments»**, columna **«Voucher Number»**. El mismo campo
está en el formulario del pago del POS (*Punto de Venta > Pedidos > Pagos*) y
como columna opcional en la conciliación bancaria:

![Pedido del POS en el backend con la columna Voucher Number](../static/description/04_backend_pedido.png)
