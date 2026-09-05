- **El campo almacenado se calcula desde un metodo decorado con `@api.constrains` en vez de
  `@api.depends`.** Se midio en Odoo 19 que **funciona**: el campo se llena al crear el pedido y al
  escribir el disparador (`date_order`), que es el comportamiento que hay hoy en produccion. Aun
  asi no es la forma canonica de declarar un campo calculado almacenado. Cambiar el decorador
  recalcularia los datos historicos, asi que queda como decision pendiente del usuario.
- **Falta `static/description/icon.png`.** En la ficha de Apps se ve el cubo generico de Odoo. Hace
  falta arte, no se inventa.
