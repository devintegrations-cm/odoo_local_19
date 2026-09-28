## Limitaciones conocidas

- **Oculta el botón estándar de propina.** La plantilla reemplaza el botón *Propina* de Odoo, y los
  botones nuevos solo salen con la casilla del módulo marcada. Con el módulo instalado y la casilla
  desmarcada, no hay forma de agregar propina desde la pantalla de pago. Es el mismo comportamiento
  de la 17.
- **Redondeo a enteros.** `Math.round` quita los decimales de la propina. Correcto para pesos
  colombianos; en una moneda con centavos no lo sería.
- **Resaltado por monto.** Un botón se resalta si la propina de la orden es igual a su valor. Si
  dos porcentajes dan el mismo monto (por ejemplo, en órdenes muy chicas), se resaltan los dos.
- Los valores de cada botón solo se muestran cuando la orden ya tiene propina.
- Los textos del ajuste (*Add buttons with percentage for tip*, *Tip % (Option 1)*...) están en
  inglés y el módulo no trae traducciones. En el POS el botón sale como *Propina* porque usa la
  palabra *Tip*, que ya traduce Odoo.
- El ajuste se puede cambiar con la sesión abierta, pero el POS lo toma recién al volver a entrar.
- No hay tests automáticos. El comportamiento del POS se valida a mano en el navegador.
- Falta `static/description/icon.png`: en *Aplicaciones* se ve el ícono genérico de Odoo.

## Componentes

- `models/pos_order.py`: pese al nombre, hereda `pos.config` y agrega `iface_tippercent`,
  `tip_percent1`, `tip_percent2` y `tip_percent3`.
- `models/res_config_settings.py`: los campos relacionados en Ajustes, con prefijo `pos_` porque
  `res.config.settings` es compartido por todos los módulos.
- `views/pos_order.xml`: el ajuste, insertado después de `setting[@id='iface_tipproduct']` y
  visible solo con *Propinas* activado.
- `static/src/xml/pos_payment.xml`: hereda `point_of_sale.PaymentScreenButtons` y reemplaza el
  botón `addTip` por los botones de porcentaje (o por un botón *Propina* equivalente al estándar si
  los tres porcentajes están en 0).
- `static/src/js/pos_payment.js`: parche de `PaymentScreen` con `addTip1..3`, `getTipX`
  (cálculo), `shouldHighlight` (resaltado) y `addTipPercent`, que llama a `this.pos.setTip()` del
  núcleo y ajusta la línea de pago seleccionada.
- Los campos llegan al POS sin cargador propio: `pos.config` no define `_load_pos_data_fields` y el
  POS lee todos sus campos.

## Notas para mantenimiento

- **Depende del botón del núcleo.** El XPath busca `//button[@t-on-click='addTip']` en
  `PaymentScreenButtons`. Si Odoo cambia ese botón, la herencia falla al cargar el POS.
- **API del núcleo usada**: `order.priceIncl`, `order.amountTaxes`, `order.getTip()`,
  `pos.setTip()`, `paymentLine.isElectronic()`, `getPaymentStatus()`, `getAmount()` y
  `setAmount()`. En la 17 se llamaban `get_total_with_tax`, `get_total_tax`, `get_tip` y
  `set_tip`.
- **Diferencia con la 17.** En la 17 el módulo ponía la propina en 0 y la volvía a calcular, sin
  tocar las líneas de pago. En la 19 copia el comportamiento del botón estándar `addTip`: ajusta la
  línea de pago seleccionada por la diferencia. El valor de la propina calculado es el mismo.
- `getTip()` devuelve la propina sin impuestos; la base resta la propina sin impuestos del subtotal.
  Si el producto de propina tuviera impuestos, el cálculo seguiría siendo sobre la base sin
  impuestos de los demás productos.
