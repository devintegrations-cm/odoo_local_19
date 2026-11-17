## 19.0.1.0.2

- Corregido: **Agregar información** en la ficha del pago no abría y mostraba «¡Vaya! Ocurrió un
  error» (`TypeError: _field_options() takes 0 positional arguments but 1 was given`). En la
  migración, la lista de conceptos del asistente pasó de calcularse una vez al cargar el módulo
  (`selection=cargar_opciones()`) a una función (`selection=_field_options`). Odoo 19 llama a esa
  función pasándole el modelo como argumento, y la función no lo aceptaba. Ahora recibe el modelo y
  lo ignora. Sin este arreglo no hay forma de completar a mano el desglose de un voucher, cosa que
  en 17 sí se podía (evidencia CRE4 de QA en staging). No cambia el cobro con el datáfono.
- Tests de regresión: el asistente ofrece los conceptos del datáfono y agrega la fila al pago.

## 19.0.1.0.1

- Propina prorrateada en pagos parciales: posición 40 + 81 = monto de la línea, como en 17.
- La posición 84 vuelve a `0` (trama certificada de 17).
- Monto aprobado = posición 40; la 80 es *Compra Neta*, no propina.
- Código 13 (tiempo agotado del datáfono) deja la venta pendiente de recuperar en vez de permitir
  otro cobro.
- El grupo *Impoconsumo* (impuesto 61, el IAC de 17) se clasifica como IAC.

## 19.0.1.0.0

- Migración a Odoo 19.
