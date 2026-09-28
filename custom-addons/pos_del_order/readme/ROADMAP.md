## Limitaciones conocidas

- **El control vive en el navegador.** No hay validación en el servidor: quien llame por RPC a
  `pos.order` puede cancelar una orden aunque no esté en la lista. Un control real necesitaría una
  validación en `pos.order` o usar los roles de `pos_hr` (permisos avanzados, básicos y mínimos),
  que son el mecanismo nativo de Odoo 19.
- **Flujos de Odoo que no pasan por la regla.** El módulo intercepta `beforeDeleteOrder`, que usan
  el ícono de *Órdenes* y *Cancelar orden*. Estos flujos llaman a `deleteOrders` directamente y no
  quedan restringidos: *Transferir / Fusionar* (la orden de origen se elimina después de pasar sus
  líneas a la de destino), *Liberar la mesa* (solo con la orden vacía), la opción *Cancelar
  órdenes* del cierre de sesión cuando quedan órdenes abiertas y la sincronización entre
  dispositivos del restaurante.
- **Sin "Iniciar sesión como empleado" la regla compara ids distintos.** Sin `pos_hr` activo en el
  punto de venta, `getCashier()` devuelve el usuario (`res.users`) y el módulo compara su id con
  ids de empleados. Si la lista quedó cargada de antes, el resultado no es confiable. El campo se
  oculta en Ajustes en ese caso, pero el valor guardado se conserva.
- La fila de Ajustes no tiene texto de ayuda: el significado de la lista vacía solo se ve en el
  marcador "Todos los empleados".
- El aviso está escrito en español en el código. Está marcado con `_t`, pero el módulo no trae
  archivos de traducción.
- Falta `static/description/icon.png`: en *Aplicaciones* se ve el ícono genérico de Odoo.

## Componentes

- `models/pos_config.py`: el campo `able_del_employee_ids` (Many2many a `hr.employee`, tabla
  `pos_config_able_del_employee_rel`).
- `models/res_config_settings.py`: el campo relacionado `pos_del_able_employee_ids`, escribible
  (`readonly=False`), que usa la pantalla de Ajustes.
- `views/res_config_settings_views.xml`: la fila *Borrar pedidos POS*, insertada después de
  *Permisos avanzados* de `pos_hr`.
- `static/src/app/services/pos_store.js`: parche de `PosStore.beforeDeleteOrder()`. Si el empleado
  no está autorizado, muestra el aviso y devuelve `false` antes de delegar en Odoo. Define
  `isEmployeeAllowedToDeleteOrders()`, que usa también la pantalla de órdenes.
- `static/src/app/screens/ticket_screen/ticket_screen.js`: parche de
  `TicketScreen.shouldHideDeleteButton()` para ocultar el ícono.
- El campo llega al POS sin cargador propio: `pos.config` no define `_load_pos_data_fields` y el
  POS lee todos sus campos.

## Notas para mantenimiento

- **Cambio respecto de Odoo 17.** En 17 el control estaba en `TicketScreen.onDeleteOrder()`, y el
  botón *Cancelar orden* de la pantalla de productos (`control_buttons.js`, que llama a
  `pos.onDeleteOrder`) lo saltaba. En 19 el control está en `beforeDeleteOrder`, por donde pasan
  los dos caminos.
- **La lista se lee de `config.raw`.** El store solo tiene cargados algunos empleados, y el getter
  relacional podría no resolver los demás. Por eso el módulo usa los ids crudos.
- **Tests.** `tests/test_delete_order_access.py` cubre la configuración: lista vacía por defecto,
  que Ajustes escriba en `pos.config` y que el relacionado sea escribible. El comportamiento en el
  POS no tiene test automático: se valida a mano en el navegador.
- En `doc/historial_16_17/` quedan las notas de la migración 16→17, solo como historial.
