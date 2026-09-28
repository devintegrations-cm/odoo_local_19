## Limitaciones conocidas

- **El rango solo se controla en la pregunta del módulo.** Los botones de comensales de
  `pos_restaurant` (pantalla de productos y pantalla de pago) permiten poner cualquier número mayor
  que cero después de responder.
- **El valor inicial no obliga a pensar.** La ventana sale con el número que ya tenía la orden (en
  mesas, los asientos), y basta con pulsar *Confirmar* para aceptarlo.
- Los textos de la pregunta y del aviso están escritos en español dentro del código; no hay
  traducción al inglés.
- El número se pide para la orden completa. Al dividir la cuenta, `pos_restaurant` resta un comensal
  a la orden original por cada cuenta separada; este módulo no interviene en ese reparto.

## Componentes

- `models/pos_config.py`: los tres campos de `pos.config` y la restricción del rango
  (`_check_number_customers_range`).
- `models/res_config_settings.py`: los campos relacionados en Ajustes, con prefijo `pos_` porque
  `res.config.settings` es compartido por todos los módulos.
- `views/res_config_settings_views.xml`: el ajuste *Número de clientes*, insertado después de
  *Permitir dividir la cuenta* (`iface_splitbill`).
- `static/src/app/utils/order_payment_validation.js`: dos parches. `PaymentScreen.setup()` pregunta
  en `onMounted`, al entrar a la pantalla de pago. `OrderPaymentValidation.askBeforeValidation()`
  pregunta al validar si todavía no se respondió; devolver `false` detiene la validación. La
  pregunta usa `NumberPopup` con `makeAwaitable` y guarda con `order.setCustomerCount()`.
- Los campos llegan al POS sin cargador propio: el POS lee todos los campos de `pos.config`.

## Notas para mantenimiento

- **Marca de "ya preguntado".** `customer_count` no sirve para saber si se preguntó, porque
  `pos_restaurant` lo inicia en 1 al crear la orden. Por eso el JS usa `order._customersAsked`, que
  no se guarda en el servidor.
- **Puntos del core que usa.** `askBeforeValidation()` es el gancho que Odoo 19 deja vacío para
  validaciones previas; `l10n_es_pos` lo usa igual. `validateOrder()` lo llama tanto desde la
  pantalla de pago como desde el pago en un clic (`validateOrderFast`). Si cambia de nombre, la
  pregunta deja de salir sin ningún error.
- **Cambios frente a la 17.** La 17 parcheaba `Order.pay()`, que en la 19 no existe, y tenía el
  rango 1–20 fijo en el JS. Se eliminó `security/ir.model.access.csv`, que no estaba en `data` y
  apuntaba a un modelo inexistente. La vista de Ajustes cambió de xmlid; al actualizar, Odoo borra
  la vista vieja.
- **Tests.** `tests/test_number_customers_config.py` cubre la configuración: valores por defecto,
  rechazo de rangos inválidos, escritura desde Ajustes y el prefijo `pos_`. La pregunta del POS no
  tiene test automático: se valida a mano en el navegador.
- Falta un recibo impreso en esta documentación: mostrarlo exige pagar una orden de prueba. La línea
  *Mesa N, Comensales: X* es de `pos_restaurant` (`receipt_header_patch.js`).
