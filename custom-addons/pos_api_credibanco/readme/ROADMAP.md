## Limitaciones conocidas

- **Validación con el datáfono real pendiente.** La base local tiene ventas aprobadas por un
  datáfono (respuestas completas con franquicia, recibo y terminal), pero la anulación, la
  recuperación y el cobro con propina no están validados de punta a punta con el terminal. Hay que
  probarlos en cada tienda antes de habilitar el método.
- **Propina cobrada.** El monto de la línea aprobada es la posición 40 (valor total) más la 80
  (propina). Si el 40 del datáfono ya incluye la propina, se contaría dos veces. En 17 se sumaban
  el 40 y el 81, que la respuesta de compra no trae. Confirmar con una compra real con propina.
- **POS por https.** Con https el navegador usa `wss://`, y el puente actual no tiene TLS: ningún
  cobro conecta. En 17 la URL era siempre `ws://`. Hoy el POS tiene que abrirse por http en la red
  local, o el puente necesita TLS.
- **Anular solo antes de validar.** El botón *Revertir* existe solo en la pantalla de pago y se
  pierde al enviar otra línea electrónica. Con *Validar órdenes de forma automática* activo, un pago
  que cubre todo el pedido lo valida enseguida y ya no se puede anular desde el POS. Los pedidos de
  reembolso tampoco pasan por el datáfono: el monto negativo se rechaza ("El monto a pagar debe ser
  mayor que 0").
- **Desglose solo al crear el pago.** La respuesta se convierte en desglose y en voucher en el
  `create` de `pos.payment`. Si el pago ya estaba sincronizado (pedido de restaurante guardado antes
  de pagar) y llega como `write`, se guarda la respuesta cruda pero no el desglose ni el voucher.
- **Respuestas compartidas.** El puente reenvía cada respuesta a todas las conexiones abiertas. El
  POS solo acepta una respuesta de venta si trae su caja (42) y su número de transacción (53), y una
  anulación de un pago aprobado si trae su recibo (43). Las respuestas de recuperación y de
  anulación de una venta en curso no traen esos datos y se aceptan tal cual: dos cajas sobre el
  mismo puente podrían cruzarlas.
- **Puente sin autenticación** en la red local, y escribe en su salida estándar lo que recibe y lo
  que responde el datáfono (incluidos datos de la tarjeta).
- **Impuestos mixtos.** Si el pedido tiene al menos un impuesto IVA o INC, los impuestos de otros
  grupos no se informan y el cobro sigue sin aviso.
- **Cajero (83).** Viaja el primer nombre del cajero, recortado a 12 caracteres. Falta confirmar
  qué espera el banco para la conciliación.
- Los códigos de error de E/S del puente (`MSG_CODE_1`, `MSG_CODE_2`) no están mapeados porque no
  se confirmó su código en la respuesta: salen con el mensaje genérico de rechazo.
- **Interfaz.** La lista *Credibanco Settings* muestra todos los métodos de pago sin filtrar, con
  títulos en inglés (*Payment terminal name*, *Ip host POS*) y la acción se llama *Credibanco
  Terminals*. En el formulario, el texto sobre el número de caja ocupa la columna de etiquetas y
  deja *Espera de respuesta (s)* desalineado (ver captura). Los mensajes del POS están en español en
  el código, sin traducción.

## Componentes

- `models/pos_payment_methods.py`: terminal `credibanco` en la selección del núcleo, campos del
  datáfono, validaciones, carga al POS (`_load_pos_data_fields`), mapa de impuestos por grupo
  (`get_credibanco_tax_map`) y reserva de números de transacción
  (`reserve_credibanco_transaction_numbers`).
- `models/pos_payment.py`: campos `credibanco_*` del pago (aprobación, respuesta, venta pendiente,
  valores enviados en 42/53/83, marca de anulación) y el `create` que genera el desglose.
- `models/pos_payment_credibanco.py` y `static/data/fields_credibanco.json`: filas del desglose y
  etiquetas de cada posición de la respuesta.
- `wizard/`: *Agregar información*, solo para responsables del POS.
- `views/`: menú *Credibanco Settings*, bloque del método de pago y bloque de la ficha del pago.
- `static/src/app/utils/payment/credibanco_protocol.js`: trama, LRC, límites por campo, lectura de
  respuestas y mensajes por código. Sin dependencias de Odoo.
- `static/src/app/utils/payment/credibanco_transport.js`: WebSocket con espera, una petición a la
  vez y correlación de respuestas.
- `static/src/app/utils/payment/credibanco_terminal.js`: la terminal (`PaymentInterface`)
  registrada como `credibanco`: venta, cancelación, anulación con línea negativa y recuperación.
- `static/src/app/screens/payment_screen/`: recuperación al abrir la pantalla, bloqueos de borrado
  y de validación, bloqueo de *Forzar terminación* y texto del botón (*Enviar a Datafono* /
  *Recuperar venta*).
- `static/src/app/components/popups/text_list_popup/`: diálogo *Valores de la transacción*.
- `migrations/19.0.1.0.0/pre-migration.py`: `enable_pos_credibanco` → `use_payment_terminal`.
- `api_credibanco-main/`: código, recursos (`tcpIp.ini`, `tef.ini`, `fields.ini`,
  `functionsFields.ini`) y guía de instalación del puente. Odoo no lo carga.
- `tools/credibanco_fake_terminal.py`: simulador de datáfono para desarrollo
  (`--outcome approved|rejected|no-answer|recover-then|bad-lrc`, `--selftest`). Odoo no lo carga.
- `doc/historial_17/`: notas de la migración 16 → 17 (se conservan como historial).

## Notas para mantenimiento

- **La trama es la certificada.** El número de caja (42 = sesión + cajero), el orden de los campos
  y el LRC reproducen lo que enviaba Odoo 17. No se rellenan ni se recortan valores: el puente
  rellena cada campo a su longitud (`fields.ini`) y un valor que no cabe se rechaza con mensaje.
- **`sendPaymentReversal` devuelve `false` a propósito** aunque la anulación se apruebe. Con `true`
  el núcleo dejaría la línea en 0 con estado *reversed*, y al cierre no habría asiento que
  conciliar. Con `false` queda el `+X` original y la línea `-X` de la anulación.
- **Anulación y recuperación repiten lo enviado.** Leen 42/53/83 de los campos guardados en el
  pago, no los recalculan desde la sesión.
- **`canForceDone`** (en `payment_lines.js`) no lo llama ninguna plantilla del núcleo 19: el
  bloqueo real de *Forzar terminación* es el parche de `sendForceDone` en `payment_screen.js`.
- **`fastPayments` es `false`**: el núcleo no envía la venta al agregar la línea, para dejar
  ajustar un pago parcial.
- **Overrides a vigilar** en cada actualización del núcleo: `PaymentScreen.deletePaymentLine`,
  `sendForceDone`, `OrderPaymentValidation.askBeforeValidation` y la plantilla
  `point_of_sale.PaymentScreenPaymentLines` (se reemplazan los botones de los estados `pending` y
  `retry`).
- **Tests.** `tests/test_pos_payment_method.py` tiene 33 pruebas de configuración, persistencia,
  secuencias, anulación y mapa de impuestos. El JS del POS no tiene test automático: se valida a
  mano en el navegador o con el simulador.
