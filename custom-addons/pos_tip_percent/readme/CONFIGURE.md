Ir a *Punto de venta › Configuración › Ajustes*, elegir el punto de venta en la parte superior y
buscar el bloque **Pago**. El ajuste del módulo está justo después del ajuste **Propinas** de Odoo.

![Punto de venta › Configuración › Ajustes › Pago: Propinas de Odoo y botones de porcentaje del módulo](../static/description/01_configuracion.png)

- **Propinas** (Odoo, campo `iface_tipproduct`). Obligatorio. Sin él no se ve el ajuste del módulo.
  Al activarlo, Odoo propone el **Producto de propina** (`tip_product_id`); en esta base es
  *[TIPS] Propinas*. El módulo usa ese producto para la línea de propina.
- **Add buttons with percentage for tip** (campo `iface_tippercent` de `pos.config`). Obligatorio
  para que el módulo actúe; desmarcado por defecto. Al marcarlo aparecen los tres porcentajes.
- **Tip % (Option 1)**, **(Option 2)** y **(Option 3)** (campos `tip_percent1`, `tip_percent2` y
  `tip_percent3`). Opcionales; 0 por defecto. Cada porcentaje distinto de 0 es un botón en la
  pantalla de pago. Un porcentaje en 0 no muestra botón.
- **Base del calculo** (campo `tip_percent_base`). *Total sin impuestos* (por defecto, igual que en
  la 17) o *Total con impuestos*. En ambos casos se descuenta la propina ya cargada.
- **Decimales** (campo `tip_percent_decimals`, 0 a 6). 0 por defecto: redondea a la unidad, igual que
  en la 17.

A tener en cuenta:

- El botón estándar **Propina** de Odoo (teclado para escribir el valor) se oculta solo cuando la
  casilla del módulo está marcada y hay al menos un porcentaje distinto de 0. En cualquier otro caso
  se ve el botón estándar. En la 17, con *Propinas* activado y la casilla desmarcada, no quedaba
  ningún botón de propina; en staging las 16 cajas con *Propinas* tienen también la casilla marcada.
- Al desmarcar *Propinas* en Ajustes, Odoo deja vacío el producto de propina y los botones del
  módulo desaparecen, aunque su casilla siga marcada.
- La configuración es **por punto de venta**. Hay que repetirla en cada tienda.
- Los cambios se ven en el POS después de volver a entrar a la sesión desde el backend.
- *Agregar propina después del pago* es otra función de Odoo (restaurante) y no interviene en este
  módulo.
