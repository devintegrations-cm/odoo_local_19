## Dependencias

- `point_of_sale` (Odoo 19 Community). No requiere otros módulos ni librerías de Python adicionales.
- El punto de venta necesita un método de pago de efectivo con **conteo de caja** (`is_cash_count`):
  el resumen de efectivo y la diferencia se calculan sobre ese método, igual que en Odoo.
- `pos_cash_in_out_message`, de este mismo repositorio, depende de este módulo y usa sus avisos
  dentro de su diálogo de confirmación.

## Pasos de instalación

Instalar *Pos Closing Validation* desde *Aplicaciones*. El módulo agrega campos a la configuración
del punto de venta, a la sesión y a las líneas de extracto, y los archivos del POS. No crea menús
ni permisos nuevos. Después de instalar o actualizar, **volver a entrar al POS** desde el backend
para que cargue los archivos nuevos.

## Migración desde Odoo 17

- Los campos de configuración conservan su nombre técnico (`maximum_cash_in_out_moves`,
  `cash_difference_exceeded_message`, `enable_rescue_session_validation`), por lo que la
  configuración existente se mantiene sin script de datos. Lo mismo vale para la marca
  `pos_cash_move` de los movimientos ya registrados.
- Se agrega la columna `pos_cash_move_uuid` con una restricción única por sesión. Los movimientos
  históricos quedan con el valor vacío, que no viola la restricción.
- Se eliminó la auditoría de continuidad del saldo de apertura de la 17 (campo
  `expected_opening_balance` y validación en `set_cashbox_pos`). La columna queda huérfana en la
  base y no se usa.
- En Odoo 19 el control de efectivo del punto de venta se calcula a partir de los métodos de pago;
  la validación de la 17 que lo exigía junto con un método de caja ya no hace falta.
