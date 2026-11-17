## 19.0.1.1.1

- Corregido: la fila **Movimientos de efectivo X/N** no aparecía en la ventana de cierre en los
  puntos de venta con inicio de sesión de empleados (`pos_hr`), que son todas las cajas activas
  (evidencia CIE10 de QA en staging). La fila se insertaba en el bloque estándar de efectivo, que
  `pos_hr` oculta para dibujar el suyo. Ahora se inserta en los dos bloques, a través de la
  subplantilla `pos_closing_validation.CashMoveCounterRow`, y `pos_hr` pasa a `depends` para que
  su plantilla se aplique antes que la de este módulo. Solo cambia la vista: el límite de
  movimientos y la diferencia autorizada ya se validaban en el servidor.

## 19.0.1.1.0

- Vuelve `pos.session.expected_opening_balance` con la definición de 17: el upgrade ya no borra la
  columna.
- La apertura captura el saldo esperado; la validación de continuidad pasa a
  `_set_opening_control_data` (19).
- Las revisiones de consistencia del cierre bloquean a todos los roles, como en 17.

## 19.0.1.0.0

- Migración a Odoo 19.
