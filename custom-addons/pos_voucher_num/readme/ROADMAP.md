- El campo se renombró de `vaucher_num` (errata heredada) a `voucher_num` en la
  versión 19.0.1.1.0 mediante migración `RENAME` atómico. La migración
  19.0.1.1.0 mantiene una compatibilidad temporal que acepta payloads legacy
  `vaucher_num` y los mapea a `voucher_num` con un log `WARNING`; se retirará
  en 19.0.1.2.0 junto con el DROP de las columnas huérfanas, cuando ningún
  POS con assets antiguos siga en uso.
- **Depende de `account_accountant` (Odoo Enterprise)**: el módulo extiende una
  vista de la conciliación bancaria. Sin Enterprise no se instala.
- El núcleo **no permite guardar** la casilla del método de pago con una sesión
  de POS abierta: hay que cerrar la caja para poder cambiarla.
- Falta `static/description/icon.png`. El módulo se publica sin icono propio.
- La validación acepta hasta 11 caracteres alfanuméricos, sin espacios ni
  signos. El límite no es configurable.
- Probado sobre Odoo 19.0. No es compatible con versiones anteriores.
- El módulo se instala automáticamente (`auto_install`) cuando están presentes
  sus dependencias.
