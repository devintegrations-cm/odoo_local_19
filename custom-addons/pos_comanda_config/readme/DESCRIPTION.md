Ajusta, **por punto de venta**, la comanda que el POS imprime en las impresoras de preparación
(cocina, barra). Es la plantilla `point_of_sale.OrderChangeReceipt`, la misma que heredan
`pos_restaurant` y `pos_self_order`.

En Odoo 19 la comanda trae unos 96 px en blanco arriba (`pt-5 mt-5`) y 48 px abajo (`pb-5`) que en
Odoo 17 no existían y desperdician papel térmico. Además, en español (`es_419`) Odoo imprime
«Ordenar», «Por:» y «(DUPLICAR)». El módulo:

- **Quita ese espaciado** y lo deja configurable (0 a 100 px arriba y abajo; 0 por defecto).
- Permite **ocultar la línea del empleado** («Atendido por: …»).
- Permite **ocultar el número de pedido** («Pedido # N»). La referencia grande, que en restaurante
  lleva el **piso y la mesa**, se imprime siempre.
- Imprime las **etiquetas en español**: *Pedido*, *Atendido por:*, *NOTA INTERNA*,
  *NOTA DEL CLIENTE*, *(DUPLICADO !)*. Desmarcado, vuelve el texto de Odoo con su traducción.

No cambia qué se envía a cada impresora ni cuándo, ni el recibo del cliente.
