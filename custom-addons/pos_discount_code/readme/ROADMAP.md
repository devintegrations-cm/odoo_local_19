- Devolver una venta con bono no reactiva el bono ni marca el canje como reversado.
- No hay vistas de consulta de canjes (listas, filtros); los datos se ven en cada orden.
- En el formulario de una orden pagada los campos del canje se ven editables, pero guardar un
  cambio da error: el servidor los bloquea.
- Las cajas que no se recarguen después de actualizar el módulo siguen con el JavaScript anterior.
- `static/src/js/loyalty_adapter.js` es el único archivo que usa el estado interno de
  `pos_loyalty` (`codeActivatedProgramRules`, `couponPointChanges`, `disabledRewards`,
  `_code_activated_coupon_ids`) y sus métodos internos. Al actualizar Odoo es el archivo a revisar.
- Con `odooleal` instalado, su versión 19 solo deja aplicar recompensas cuando el programa Leal
  está activo en la orden, para cualquier programa. Mientras no se corrija en ese módulo, el
  descuento del bono no llega a la orden en las cajas sin Leal. Se valida en staging junto con
  `odooleal`.
