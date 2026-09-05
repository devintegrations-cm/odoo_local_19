- El campo que guarda el número se llama `vaucher_num` en la base de datos, con
  esa **errata heredada** («vaucher» en vez de «voucher»). Renombrarlo obligaría
  a migrar los datos existentes, así que se mantuvo tal cual.
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
