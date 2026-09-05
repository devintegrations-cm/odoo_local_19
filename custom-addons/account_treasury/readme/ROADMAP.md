- **La línea del método de pago necesita cuenta de pagos pendientes.** En Odoo 19 se puede
  confirmar un pago cuya línea de método de pago no tiene cuenta de pagos pendientes configurada, y
  ese pago queda **sin asiento contable** (en Odoo 17 era imposible). Sin asiento no hay
  conciliación, y sin conciliación el módulo no encuentra las facturas cubiertas: el correo sale
  sin el detalle de facturas y los solicitantes no se notifican. Hay que configurar la cuenta en el
  método de pago del diario **antes** de registrar pagos.
- **Falta `static/description/icon.png`.** En la ficha de Apps se ve el cubo genérico de Odoo. Hace
  falta arte, no se inventa.
- **Tipo de cuenta bancaria, desactivado en 19.0.** Las vistas que agregaban *Tipo de cuenta
  bancaria* (ahorros / corriente) al partner y a su cuenta están comentadas en el manifiesto: en
  Odoo 19 el formulario de contacto ya no expone `acc_number` directamente. Quien lo necesite tiene
  que rehacerlas contra el widget de cuentas bancarias de 19.
- **Textos en español.** Las etiquetas de los campos y las plantillas de correo están escritas en
  español, sin traducción a otros idiomas.
