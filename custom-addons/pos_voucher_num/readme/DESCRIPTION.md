Pide el número de aprobación (voucher) al cobrar con tarjeta y lo guarda en la
línea de pago del punto de venta. Cuando un método de pago del POS tiene
activada la casilla **«Ask for approval number»**, el POS abre un diálogo y pide
el número de voucher *antes* de crear la línea de pago: valida que sean como
máximo 11 caracteres alfanuméricos, y si el cajero descarta el diálogo o el dato
no cumple, la línea de pago no se agrega.

El número queda visible en la línea de pago junto al importe durante todo el
cobro, se guarda en el pedido y después se consulta desde el backend. Los
métodos de pago que no tienen la casilla marcada siguen funcionando como
siempre: el módulo no interfiere con ellos.
