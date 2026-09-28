## Limitaciones conocidas

- **El nombre y la ayuda de la casilla no describen lo que hace.** El campo se llama *Habilitar
  mensaje en movimiento de Efectivo* y su ayuda dice "Pedir confirmación antes de registrar un
  movimiento de efectivo", pero la confirmación sale siempre: la casilla solo controla el mensaje.
  Es el mismo comportamiento de Odoo 17. Queda documentado y sin cambiar el código.
- En el diálogo, el ícono de información y el mensaje configurado salen en renglones separados: la
  regla `.config-message` del CSS no tiene `display: flex`, a diferencia del aviso de último
  movimiento. Es solo estético.
- Los textos del diálogo están escritos en español dentro del código, y la plantilla no los marca
  para traducción. Hoy no importa porque los POS operan en español.
- Falta `static/description/icon.png`: en *Aplicaciones* se ve el ícono genérico de Odoo.

## Componentes

- `models/pos_config.py`: los dos campos de `pos.config` y sus campos relacionados en
  `res.config.settings`. En Ajustes llevan el prefijo `pos_` porque ese modelo es compartido por
  todos los módulos, y un nombre sin prefijo podría chocar con otro.
- `views/pos_config_views.xml`: el bloque en *Ajustes › Interfaz de PdV*.
- `static/src/js/cash_move_popup_patch.js`: parche de `CashMovePopup.confirm()` que abre el
  diálogo antes de delegar en el flujo estándar.
- `static/src/js/cash_move_confirm_popup.js`, `.xml` y `.css`: el diálogo, un componente OWL sobre
  `Dialog` que se abre con `makeAwaitable` y responde por `getPayload`. Los estilos están todos
  bajo `.cash-move-confirm-popup`.
- `hooks.py`: el renombre desde Odoo 17 (ver *Instalación*).
- Los campos llegan al POS sin cargador propio: `pos.config` no define `_load_pos_data_fields` y
  el POS lee todos sus campos.

## Notas para mantenimiento

- **Dependencia con `pos_closing_validation`.** El parche usa tres métodos que ese módulo agrega
  al mismo `CashMovePopup`: `isCashMoveBlocked()`, `isLastCashMove()` y
  `setLastMoveWarningSkipped()`. Si se renombra alguno, hay que actualizar los dos módulos en el
  mismo cambio. Si el parche no encuentra esos métodos, el POS falla al pulsar *Confirmar*.
- **Tests.** `tests/test_cash_in_out_message.py` cubre la configuración: valor por defecto, que
  Ajustes escriba y lea en `pos.config`, el prefijo `pos_` y que desactivar no borre el texto. El
  diálogo del POS no tiene test automático: se valida a mano en el navegador.
- **Lección de la migración.** En Odoo 17, `assets` apuntaba a `cash_in_out_message/static/...`.
  Tras renombrar la carpeta, esas rutas dejaron de existir y el POS no cargaba nada del módulo,
  sin ningún error al arrancar. Al renombrar un módulo, las rutas de `assets` deben empezar con el
  nombre nuevo de la carpeta.
