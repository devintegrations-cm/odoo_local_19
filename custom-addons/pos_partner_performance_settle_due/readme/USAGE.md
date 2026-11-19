No hay nada que hacer en la caja. Con la opción activada, la lista de clientes del POS (en las cajas
donde está visible) ya no muestra *Total adeudado* ni las opciones *Liquidar órdenes* / *Liquidar
facturas*: `pos_settle_due` las muestra solo cuando conoce una deuda mayor que cero, y ahora no la
calcula.

La deuda de un cliente se consulta en el backend (*Contabilidad*, ficha del contacto).
