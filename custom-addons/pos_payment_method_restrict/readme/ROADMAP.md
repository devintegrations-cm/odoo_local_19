## Limitaciones conocidas

- **Pendiente de decisión: *Crear factura electrónica* no tiene efecto.** En Odoo 17 la casilla
  elegía entre factura normal y electrónica mediante `to_electronic_invoice` de Jorels. Jorels 19
  eliminó ese campo, y el POS solo lo marca si existe, así que hoy la casilla no hace nada. Se
  propuso reemplazarla por un diario opcional en cada restricción, con script de datos. Falta que lo
  confirme el líder técnico. Verificar en STG, donde la usan las restricciones que facturan con un
  diario electrónico propio.
- **Pendiente de configuración: la factura agrupada sale electrónica solo si el diario de facturas
  del POS tiene resolución DIAN.** Con Jorels 19 ya no hay un diario electrónico aparte en el punto
  de venta: la factura agrupada usa el diario de facturas del POS, y es electrónica si ese diario lo
  es. Verificar en STG antes de producción.
- **Los filtros *Esta semana* y *Este mes* de los informes dan error**, y por eso *Reporte mensual* y
  *Consumo de productos*, que abren con *Este mes*, muestran "Ocurrió un error" al entrar. Sus
  dominios usan `context_today().replace(day=1)` y `context_today().weekday()`, que el evaluador de
  dominios del navegador no soporta. En el Odoo 17 de referencia los dominios son los mismos y ese
  evaluador tampoco tiene esos métodos, así que el error viene de antes de la migración.
- **Horas y "hoy" en UTC.** El aviso de duplicado compara con la fecha del servidor y muestra la
  hora en UTC: una orden de las 2:02 p. m. en Colombia sale como 19:02. El filtro *Hoy* de los
  informes arma el rango sin convertir de zona horaria, así que probablemente también corta el día
  a las 7:00 p. m. hora de Colombia. Esto último no se comprobó con órdenes reales de la noche.
- **La restricción se muestra como `pos.payment.customer.restriction,3`** en la orden y en los
  informes, porque el modelo no tiene un campo de nombre. Pasa igual en 17.
- La lista de restricciones en *Ajustes* es angosta y corta los encabezados. Para ver todas las
  columnas conviene el menú *Configuración › Restricciones de pago*.
- Los campos `is_hotel_order`, `hotel_guest`, `hotel_room` y `hotel_data_summary` de la orden se
  calculan y guardan, pero ninguna vista los muestra.
- El requerimiento de negocio (`REQUERIMIENTO IT DESAYUNOS HOTELES.md`) pide también precios de
  convenio, combo desayuno y bebida, el descuento del 10 % para huéspedes y anulaciones con
  autorización. Este módulo no implementa esas partes.
- Falta `static/description/icon.png`: en *Aplicaciones* se ve el ícono genérico de Odoo.

## Componentes

- `models/pos_payment_customer_restriction.py` y `models/pos_payment_restriction_field.py`: la
  restricción (punto de venta, método, clientes, casillas) y los campos del popup, con la clave
  calculada desde la etiqueta.
- `models/pos_config.py`: los campos del punto de venta y `_load_pos_data_read`, que agrega al
  POS un diccionario plano de restricciones por método en `config._payment_restrictions`.
- `models/res_config_settings.py`: los campos relacionados de *Ajustes*. Su `create` escribe las
  restricciones directo en `pos.config`, porque *Ajustes* puede descartar cambios en los campos del
  popup cuando los IDs de las restricciones no cambian.
- `models/pos_order.py`: datos del popup (`restriction_data`, `restriction_id` y campos derivados),
  búsqueda de duplicados, entrega en tiempo real, la decisión de `to_invoice` en
  `_process_saved_order` y la factura agrupada.
- `static/src/js/payment_method_restrict.js`: parches de `PaymentScreen` (filtro de métodos,
  popup, duplicados), de `PosStore.selectPartner` (vuelve a aplicar la factura al cambiar el
  cliente) y de `PosOrder.serializeForORM` (envía `restriction_id`, que el POS descartaría porque su
  modelo no está cargado en el POS).
- `static/src/js/payment_restriction_popup.js` y `.xml`: el popup, un componente sobre `Dialog` que
  se abre con `makeAwaitable`.
- `views/pos_config_views.xml`: el bloque de *Ajustes*, las vistas de la restricción y el menú de
  configuración. `views/pos_hotel_report_views.xml`: la pestaña de la orden y los informes.
- `data/pos_order_server_actions.xml`: la acción *Crear factura agrupada*.

## Notas para mantenimiento

- **Tests.** `tests/test_restriction_invoice.py` cubre la decisión de `to_invoice` en el servidor
  (la restricción manda sobre lo que envía el POS, en los dos sentidos; clientes sin restricción y
  casilla general apagada no se tocan) y la factura agrupada (una sola factura con el diario del
  POS, órdenes en *Registrado*, sin refacturar). El filtro de métodos, el popup y el aviso de
  duplicado no tienen test automático: se prueban a mano en el navegador.
- **Motor propio de agrupación.** No usa `_prepare_invoice_vals` del estándar sobre todo el grupo
  porque en 19 exige un solo punto de venta, usuario y posición fiscal, y partiría la factura de un
  hotel por cajero. Lo llama sobre la primera orden del grupo: diario, posición fiscal y plazo de
  pago salen de esa orden. La fecha de la factura es la de esa orden si su sesión sigue abierta, y
  la del día si está cerrada.
- **Dos lecturas de la restricción.** Si un cliente está en varias restricciones, el POS aplica la
  primera que encuentra y el servidor la del método de pago usado. El resultado final lo decide el
  servidor.
- **Interacción con la facturación obligatoria.** La restricción debe seguir prevaleciendo en el
  servidor. Si otro módulo fuerza `to_invoice` en Python después de `_process_saved_order`, la
  factura agrupada deja de funcionar. Revisar en particular la versión 19 del módulo de fidelización
  de Jorels que usa STG.
