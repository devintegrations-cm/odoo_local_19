- El campo se renombró de `vaucher_num` (errata heredada) a `voucher_num` en la
  versión 19.0.1.1.0 mediante migración `RENAME` atómico. La migración
  19.0.1.1.0 mantiene una compatibilidad temporal que acepta payloads legacy
  `vaucher_num` y los mapea a `voucher_num` con un log `WARNING`; se retirará
  en 19.0.1.2.0 junto con el DROP de las columnas huérfanas, cuando ningún
  POS con assets antiguos siga en uso. El script de 19.0.1.2.0 solo borra una
  columna vieja si no le queda ningún dato sin copiar.
- **Pago rápido de Odoo 19** (`use_fast_payment`): no pasa por la pantalla de
  pago, así que el voucher se pide al validar
  (`OrderPaymentValidation.askBeforeValidation`). Si se cancela o el número no
  es válido, el pedido no se valida y la línea creada por el pago rápido se
  quita. Desde la pantalla de pago las líneas ya traen el voucher y no se
  pregunta dos veces.
- **El voucher no se copia al apunte contable**, igual que en la 17: los campos
  `voucher_num_account`, `pos_payment_id` y `super_voucher` de
  `account.move.line` y `pos_vouchers_nums` de `account.move` guardan el
  histórico, pero ningún código los llena (0 en los últimos 300 000 apuntes de
  la copia de producción).
- La vista de la conciliación bancaria (`views/account_move_line_list.xml`)
  está fuera del manifiesto, como en la 17.
- El núcleo **no permite guardar** la casilla del método de pago con una sesión
  de POS abierta: hay que cerrar la caja para poder cambiarla.
- Falta `static/description/icon.png`. El módulo se publica sin icono propio.
- La validación acepta hasta 11 caracteres alfanuméricos, sin espacios ni
  signos. El límite no es configurable.
- Probado sobre Odoo 19.0. No es compatible con versiones anteriores.
- No es `auto_install`: se instala a mano.
