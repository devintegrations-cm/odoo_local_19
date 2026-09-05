- **Hace falta un diario de facturas.** Si el punto de venta no puede facturar
  (sin diario de facturas configurado en *Contabilidad > Diarios por defecto*),
  el modulo no fuerza nada: forzar el flag dejaria pedidos imposibles de
  validar.
- **Facturar exige cliente.** Odoo pide un cliente en el pedido antes de
  validar una venta facturada; con este modulo activo, todos los pedidos van a
  necesitarlo.
- Falta `static/description/icon.png`. El modulo se publica sin icono propio.
- La configuracion es **por punto de venta**, no por compania ni global.
- El modulo se instala solo (`auto_install`) en cuanto esta *point_of_sale*.
