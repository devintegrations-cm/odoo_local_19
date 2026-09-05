El módulo no agrega ajustes al punto de venta ni a los Ajustes generales: toda la
configuración es la asignación de cada producto a sus cajas.

- Entrá a *Punto de Venta › Productos › Productos*.
- Abrí el producto y pasá a la pestaña **Point of Sale**.
- Junto a la categoría del POS está el campo **Puntos de venta**: agregá las cajas que tienen
  que mostrar ese producto.
- Guardá.

La pestaña **Point of Sale** solo existe si el producto tiene tildada la casilla **Point of
Sale** de la cabecera. Esa casilla es del núcleo de Odoo, no de este módulo, y es la que
habilita el producto para el punto de venta.

Después de cambiar las asignaciones no alcanza con recargar la pestaña del POS: hay que
volver a entrar al punto de venta desde el backend (*Abrir caja* / *Continue Selling*) para
que la sesión cargue la nueva lista de productos.
