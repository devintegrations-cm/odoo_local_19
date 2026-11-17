## 19.0.1.0.2

- Corregido: los informes **Consumo de productos** y **Reporte mensual** de *Punto de venta ›
  Informes › Convenios y restricciones* no abrían («¡Vaya! Ocurrió un error», evidencias PR13 y
  PR13B de QA en staging). Los filtros *Esta semana* y *Este mes* usaban
  `context_today().replace(day=1)` y `context_today().weekday()`, que el evaluador de dominios del
  navegador no soporta (tampoco el de 17: en producción el informe ya fallaba). Se reemplazan por
  `relativedelta(day=1)` y `relativedelta(weekday=0)`, que dan el mismo rango: el mes desde el día
  1 y la semana de lunes a lunes.

## 19.0.1.0.1

- Corregido: los datos capturados en el popup (p. ej. «Habitación: 101») no se mostraban debajo de
  la línea de pago, como en 17 (evidencia PR6B de QA en staging, hallazgo
  POS-PAYMENT-METHOD-RESTRICT-FE-0002). La plantilla `payment_line_restriction_data.xml` no se
  había migrado. Se porta a 19 leyendo el dato del pedido (`restriction_data` y `restriction_id`),
  porque en 19 ya no se guarda en la línea de pago. Solo cambia la pantalla: el dato ya se guardaba
  en la orden.

## 19.0.1.0.0

- Migración a Odoo 19.
