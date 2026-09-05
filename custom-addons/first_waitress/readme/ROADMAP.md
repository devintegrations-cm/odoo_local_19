- **El campo almacenado se calcula desde un metodo decorado con `@api.constrains` en vez de
  `@api.depends`.** Se midio en Odoo 19 que **funciona**: el campo se llena al crear el pedido y al
  escribir el disparador (`employee_id`), que es el comportamiento que hay hoy en produccion. Aun
  asi no es la forma canonica de declarar un campo calculado almacenado. Cambiar el decorador
  recalcularia los datos historicos, asi que queda como decision pendiente del usuario.
- **El campo `Cashier` del nucleo no vuelve redundante a este modulo.** Se evaluo darlo de baja
  contra `pos_hr` y no corresponde: *Cashier* sigue al empleado **actual** del pedido y *First
  waitress* guarda al **primero** que lo atendio.
- **Falta `static/description/icon.png`.** En la ficha de Apps se ve el cubo generico de Odoo. Hace
  falta arte, no se inventa.
