## Limitaciones conocidas

- **La fila "Movimientos de efectivo X/N" no aparece en la ventana de cierre si el punto de venta
  usa `pos_hr`.** `closing_popup_extension.xml` la inserta después del desglose de entradas/salidas
  del bloque estándar, pero con `pos_hr` activo en el punto de venta Odoo oculta ese bloque y dibuja
  una copia propia. Comprobado en el POS local, que tiene `pos_hr` activo: la plantilla heredada
  contiene la fila, pero no se muestra. Por eso no hay captura de la ventana de cierre. Verificar en
  STG qué tiendas tienen `pos_hr` activo.
- **La lista de movimientos no se puede abrir desde el POS.** `cash_move_popup.xml` elimina el
  botón *Detalles* de la ventana de entrada/salida de efectivo, y en Odoo 19 esa lista solo se abre
  desde ese botón. En consecuencia, `cash_move_list_popup_patch.js`, que oculta el borrado a los
  cajeros, no tiene efecto visible. La restricción de borrado sigue aplicándose en el servidor.
- **Las sesiones de rescate pueden no existir en Odoo 19.** El core de Odoo 19 conserva el campo
  `rescue` y lo filtra, pero no se encontró código fuera de los tests que cree una sesión con
  `rescue=True`. La validación de apertura, el bloqueo de movimientos en rescates y el enlace
  `rescue_parent_session_id` se migraron sin cambios y podrían no activarse nunca. Para comprobarlo
  en una tienda: buscar sesiones de rescate en *Punto de venta › Sesiones* después de operar.
- `rescue_parent_session_id` solo se completa si `rescue` llega en los valores de creación de la
  sesión; si una versión futura marca el rescate con una escritura posterior, el vínculo queda
  vacío.
- El rol de responsable sale del usuario de Odoo, no del empleado de `pos_hr`. En una tienda donde
  todos los empleados comparten un usuario con permisos de administrador del POS, las revisiones de
  consistencia nunca bloquean.
- Los campos nuevos de la sesión (`rescue_parent_session_id`, `rescue_session_ids`) y de las líneas
  de extracto (`pos_cash_move`, `pos_cash_move_uuid`) no se muestran en ninguna vista.
- Falta `static/description/icon.png`: en *Aplicaciones* se ve el ícono genérico de Odoo.

## Componentes

- `models/pos_config.py`: los tres campos de `pos.config`, sus relacionados con prefijo `pos_` en
  `res.config.settings`, la restricción del límite mayor que cero y el bloqueo de apertura por
  rescates pendientes (`open_ui` → `_check_rescue_sessions_before_open_ui`). Se usa `UserError` y no
  `RedirectWarning` porque el controlador `/pos/ui` descarta el valor de retorno de `open_ui()`.
- `models/pos_session.py`: límite e idempotencia (`try_cash_in_out`,
  `_prepare_account_bank_statement_line_vals`), borrado solo para responsables
  (`delete_cash_in_out`), bloqueo acotado de la fila de la sesión (`_lock_session_row`, 2 s para
  movimientos y 10 s para el cierre), validaciones de cierre (`_cannot_close_session`,
  `post_closing_cash_details`, `_check_authorized_cash_difference`) y los dos endpoints del POS,
  `get_cash_in_out_control_data` y `get_closing_validation_info`, que exigen el grupo de usuario del
  POS.
- `models/account_bank_statement_line.py`: la marca `pos_cash_move` y el identificador
  `pos_cash_move_uuid`, con restricción única por sesión declarada con `models.Constraint`.
- `views/pos_config_views.xml`: las tres opciones en *Ajustes › Pagos*, después de *Establecer la
  diferencia máxima*.
- `static/src/js/pos_store_patch.js`: controles previos a *Entrada/salida de efectivo* y a *Cerrar
  caja registradora*, y los botones de los avisos de cierre (`handleClosingError`).
- `static/src/js/cash_move_popup_patch.js` y `static/src/xml/cash_move_popup.xml`: contador,
  resumen, aviso de último movimiento, bloqueo por límite, avisos sin conexión y el identificador
  del movimiento.
- `static/src/js/cash_move_list_popup_patch.js`: oculta el borrado a quien no es responsable (ver
  *Limitaciones conocidas*).
- `static/src/xml/closing_popup_extension.xml`: la fila de movimientos en la ventana de cierre (ver
  *Limitaciones conocidas*).

## Notas para mantenimiento

- **Contrato con `pos_cash_in_out_message`.** Ese módulo parcha el mismo `CashMovePopup` y usa
  `isCashMoveBlocked()`, `isLastCashMove()`, `setLastMoveWarningSkipped()`, `getCashMoveControl()`,
  `pos.closingValidationInfo` y `confirm()` encadenado con `super`. Renombrar cualquiera obliga a
  cambiar los dos módulos en el mismo commit.
- **Todas las reglas se deciden en el servidor**; el POS solo las muestra. Un aviso quitado del JS
  no habilita nada que el servidor rechace.
- `get_closing_control_data` de Odoo no se sobreescribe a propósito: agregar claves a su respuesta
  hace que OWL rechace las props de la ventana de cierre estándar.
- El resumen usa los cálculos de Odoo: el efectivo esperado es `cash_register_balance_end` y la
  diferencia es `cash_register_difference`. Las entradas/salidas del resumen suman todas las líneas
  de caja de la sesión por signo; el contador del límite solo cuenta las marcadas con
  `pos_cash_move`.
- Las cadenas de nivel de módulo usan `_lt`: con `_` en tiempo de importación Odoo 19 no detecta el
  idioma y guarda el texto sin traducir.
- **Tests.** `tests/test_closing_validation.py` tiene 66 tests: resumen y su igualdad con
  `cash_register_balance_end`, límite, idempotencia, contrato del bloqueo acotado, diferencia
  autorizada para todos los roles, política por rol con nota de auditoría, borrado restringido,
  rescates y apertura bloqueada. La concurrencia real no se puede probar en `TransactionCase`: se
  prueba el contrato SQL y se simula el fallo del bloqueo. El JS del POS no tiene tests
  automáticos.
- Los comentarios de `_filter_non_empty_rescues` y `create` en `pos_session.py` remiten al
  `README.md` anterior; ese contenido está ahora en *Limitaciones conocidas*.
