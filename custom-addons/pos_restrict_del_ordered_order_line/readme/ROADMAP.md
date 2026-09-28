## Limitaciones conocidas

- **El control vive en el navegador.** No hay validación en el servidor: `ordered_quantities` es
  escribible y quien envíe la orden por RPC puede cambiar cantidades o borrar líneas. Si el POS no
  terminó de cargar, el módulo deja pasar la acción.
- **Pago marca líneas no enviadas.** El parche de `PosStore.pay()` guarda las cantidades ordenadas
  antes de que `pos_restaurant` pregunte si se envía el pedido, así que *Descartar* no lo evita. En
  Odoo 17 el botón de pago llamaba a `order.pay()` y no marcaba líneas: es un cambio de
  comportamiento de la migración.
- **Flujos de Odoo que no pasan por el control.** El módulo intercepta `setQuantity`,
  `removeOrderline` y `updateQuantityNumber`. No quedan restringidos: *Transferir / Fusionar* mesas
  (si la línea se suma a otra existente, la cantidad ordenada de origen no se suma), *Cancelar orden*
  y *Liberar la mesa* (eliminan la orden entera; para eso está `pos_del_order`) ni la división de
  cuenta.
- **La cantidad ordenada no baja con una reducción autorizada.** Queda en el valor anterior hasta el
  próximo envío o pago.
- **Sin "Iniciar sesión como empleado" la regla compara ids distintos.** `getCashier()` devuelve el
  usuario (`res.users`) y el módulo compara su id con ids de empleados. El campo se oculta en Ajustes
  en ese caso, pero el valor guardado se conserva y sigue aplicando.
- El texto de ayuda de Ajustes menciona "borrar pedidos", que es la función de `pos_del_order`.
- Los textos están en español en el código; el aviso usa `_t` pero el módulo no trae archivos de
  traducción. El título *Operacion no permitida* va sin tilde.
- `static/description/icon.png` mide 750x750 px; la norma pide 100x100 como los módulos del core.
- No hay tests automáticos.

## Componentes

- `models/pos_config.py`: el campo `able_del_pol_employee_ids` (Many2many a `hr.employee`, tabla
  `abl_pol_employee_ids`).
- `models/res_config_settings.py`: el campo relacionado `pos_able_del_pol_employee_ids`, escribible,
  que usa la pantalla de Ajustes.
- `models/pos_order.py`: el campo `ordered_quantities` de `pos.order.line` y su alta en
  `_load_pos_data_fields` para que viaje al POS y se guarde al sincronizar.
- `views/res_config_settings_views.xml`: la fila de Ajustes, dentro del bloque
  `multiple_employee_session` de `pos_hr`.
- `views/pos_order_view.xml`: la columna opcional *Ordered Quantities* en las líneas de la orden.
- `static/src/js/models.js`: parches de `PosOrderline.setQuantity()`, `PosOrder.removeOrderline()`
  y `OrderSummary.updateQuantityNumber()`, y la regla `isCapableToDeletePosOrderLines()`.
- `static/src/js/pos_store.js`: parche de `PosStore.submitOrder()` y `PosStore.pay()` que guarda las
  cantidades ordenadas, y expone el store a los modelos (`posRestrictState`).
- `static/src/js/split_bill_screen.js`: parche de `SplitBillScreen.createSplittedOrder()`.
- `static/src/js/orderline.js`, `static/src/xml/orderline.xml`, `static/src/css/orderline.scss`: el
  distintivo *En preparación* con los botones de restar y sumar.

## Notas para mantenimiento

- **Qué es "línea ordenada".** Es el campo propio `ordered_quantities`, no un concepto de Odoo. No
  coincide con `uiState.savedQuantity` (cantidad sincronizada) ni con
  `last_order_preparation_change` (lo que Odoo ya notificó a cocina).
- **El parche de `updateQuantityNumber` hoy no se ejecuta.** Ese camino solo se usa cuando
  `PosStore.disallowLineQuantityChange()` devuelve `true`; en Odoo 19 Community devuelve `false` y
  ningún módulo de Community lo cambia. Queda como defensa si se instala uno que lo active.
- **Cambio respecto de Odoo 17.** El envío a cocina pasó de `ActionpadWidget.submitOrder()` a
  `PosStore.submitOrder()`, la división de `proceed()` a `createSplittedOrder()`, y el aviso de
  `ErrorPopup` a `AlertDialog`. En 19 `setQuantity` devuelve el error y quien la llama muestra el
  diálogo; el borrado con ⌫ va directo a `removeOrderline`, por eso hay dos parches.
- **El identificador de la vista de Ajustes** (`res_config_settings_view_form_inh_pos_del_order_17`)
  viene de 17 y menciona `pos_del_order`, pero pertenece a este módulo. No renombrarlo sin revisar
  el efecto en la actualización.
