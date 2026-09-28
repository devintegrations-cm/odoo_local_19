Reemplaza el botón **Propina** de la pantalla de **Pago** del Punto de Venta por hasta **tres botones
de porcentaje** configurables por punto de venta (por ejemplo, 5 %, 10 % y 20 %). Al pulsar uno, el
POS calcula la propina sobre el subtotal de la orden y la agrega como una línea del producto de
propina, sin que el cajero tenga que hacer la cuenta ni escribir el valor.

Relación con Odoo 19: la propina es del núcleo (`point_of_sale`). Odoo trae un solo botón
**Propina** que abre un teclado para escribir el valor a mano. Este módulo no cambia cómo se guarda
la propina: usa el mismo producto de propina y el mismo método del núcleo (`setTip`), así que la
línea de propina y el total quedan igual que con el botón estándar.

Cómo se calcula, según el código (`static/src/js/pos_payment.js`):

- **Base: subtotal sin impuestos y sin la propina actual.** Total con impuestos, menos impuestos,
  menos la propina que ya tenga la orden. En la captura de *Uso*, dos hamburguesas suman $ 66.640
  con $ 10.640 de impuestos; la base es $ 56.000 y el 10 % da $ 5.600.
- **Redondeo a unidades enteras** de la moneda (`Math.round`). En pesos colombianos no se nota; en
  una moneda con centavos, la propina pierde los decimales.
- **Un solo valor de propina por orden.** Pulsar otro porcentaje reemplaza el anterior; no se suman.
