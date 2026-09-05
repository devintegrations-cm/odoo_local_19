- **Requisito de despliegue: asigná productos antes de instalar.** Con el módulo instalado, un
  punto de venta que no tenga ni un producto asignado **deja de abrir**: el intento termina en
  un error (*«There is no product linked to your PoS»*, que desde el navegador se ve como un
  error 422). Antes de instalarlo en producción hay que recorrer todas las cajas y dejar cada
  una con su lista de productos.
- **El filtro es visual.** Oculta de la pantalla de productos lo que no corresponde a esa
  caja, pero no impide que un producto ajeno llegue al pedido por otras vías del núcleo de
  Odoo: un ítem de combo, un pedido ya abierto en una mesa, un código de barras. Es
  deliberado: esos productos tienen que seguir cargados en la sesión, porque quitarlos del
  todo dejaría sin registro a los pedidos en curso y rompería la mesa. El objetivo del módulo
  es que el cajero no vea lo que no vende, no bloquear la venta.
- **Convive con el límite de categorías del núcleo.** Si el punto de venta tiene categorías
  restringidas en sus ajustes, se aplican los dos filtros a la vez: se muestra lo que esté
  asignado a esa caja *y* pertenezca a una categoría permitida.
- **El campo es por plantilla de producto.** Todas las variantes de un producto siguen la
  asignación de su plantilla; no se puede habilitar una variante en una caja y otra en otra.
- Falta `static/description/icon.png`: el módulo se muestra con el icono genérico de Odoo.
