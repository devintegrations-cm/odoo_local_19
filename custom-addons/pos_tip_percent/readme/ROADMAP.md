## Limitaciones conocidas

- **Oculta el botón estándar de propina** cuando hay porcentajes configurados: no se puede escribir
  un valor libre en esas cajas.
- **Redondeo a enteros** por defecto; se ajusta con *Decimales*.
- **Resaltado por monto.** Un botón se resalta si la propina de la orden es igual a su valor. Si
  dos porcentajes dan el mismo monto (por ejemplo, en órdenes muy chicas), se resaltan los dos.
- Los textos del ajuste (*Add buttons with percentage for tip*, *Tip % (Option 1)*...) están en
  inglés y el módulo no trae traducciones. En el POS el botón sale como *Propina* porque usa la
  palabra *Tip*, que ya traduce Odoo.
- El ajuste se puede cambiar con la sesión abierta, pero el POS lo toma recién al volver a entrar.
- No hay tests automáticos. El comportamiento del POS se valida a mano en el navegador.
- Falta `static/description/icon.png`: en *Aplicaciones* se ve el ícono genérico de Odoo.

## Componentes

- `models/pos_order.py`: pese al nombre, hereda `pos.config` y agrega `iface_tippercent`,
  `tip_percent1`, `tip_percent2`, `tip_percent3`, `tip_percent_base` y `tip_percent_decimals`.
- `models/res_config_settings.py`: los campos relacionados en Ajustes, con prefijo `pos_` porque
  `res.config.settings` es compartido por todos los módulos.
- `views/pos_order.xml`: el ajuste, insertado después de `setting[@id='iface_tipproduct']` y
  visible solo con *Propinas* activado.
- `static/src/xml/pos_payment.xml`: hereda `point_of_sale.PaymentScreenButtons`, oculta el botón
  `addTip` cuando hay porcentajes y agrega los botones de porcentaje a continuación.
- `static/src/js/pos_payment.js`: parche de `PaymentScreen` con `addTip1..3`, `getTipBase`,
  `roundTip`, `getTipX` (cálculo), `shouldHighlight` (resaltado) y `addTipPercent`, que solo llama a
  `this.pos.setTip()` del núcleo.
- Los campos llegan al POS sin cargador propio: `pos.config` no define `_load_pos_data_fields` y el
  POS lee todos sus campos.

## Notas para mantenimiento

- **Depende del botón del núcleo.** El XPath busca `//button[@t-on-click='addTip']` en
  `PaymentScreenButtons`. Si Odoo cambia ese botón, la herencia falla al cargar el POS.
- **API del núcleo usada**: `order.priceIncl`, `order.priceExcl`, `line.prices`, `pos.setTip()`,
  `pos.currency.round/isZero/equal` y `roundDecimals` de `@web/core/utils/numbers`.
- **Igual que en la 17, no toca las líneas de pago.** La versión anterior de la 19 copiaba el botón
  estándar `addTip` y sumaba la propina a la línea seleccionada sin descontar el cambio: con
  efectivo y cambio, el pago registrado superaba lo recibido (POS-TIP-PERCENT-FE-0001).
- `getTip()` devuelve la propina sin impuestos; la base resta la propina sin impuestos del subtotal.
  Si el producto de propina tuviera impuestos, el cálculo seguiría siendo sobre la base sin
  impuestos de los demás productos.
