# POS Cash In/Out Message

Añade un **popup de confirmación** antes de registrar un movimiento Cash In/Out en el Punto de Venta, con el monto, el tipo de movimiento y un **mensaje configurable** por punto de venta.

Depende de `pos_closing_validation` (usa sus reglas de límite de movimientos).

## Configuración

**Ajustes → Punto de Venta → PoS Interface**

| Campo | Descripción |
|-------|-------------|
| **Mensaje en movimientos de efectivo** | Activa el popup de confirmación. |
| **Mensaje de Cash In/Out** | Texto que verá el cajero en ese popup. Vacío = sólo la confirmación, sin mensaje. |

Se guardan en `pos.config` (`cash_in_out_message_enabled`, `cash_in_out_message`) a través de los campos `pos_cash_in_out_message*` de `res.config.settings`.

## Comportamiento

- El mensaje aparece **sólo en el popup de confirmación**, no en el popup de Cash In/Out.
- Si el movimiento sería el último permitido, el aviso se muestra **dentro de este mismo popup**, con su diseño; el aviso estándar de `pos_closing_validation` se omite para no preguntar dos veces.
- Un movimiento con importe vacío o inválido no abre la confirmación: lo resuelve el popup estándar de Odoo.
- Sin conexión, el límite no se puede verificar; este popup no bloquea nada (la política de offline pertenece a `pos_closing_validation`).
- Cancelar cierra la confirmación y deja el importe escrito, para corregirlo sin empezar de nuevo.

## Estructura

| Archivo | Rol |
|---------|-----|
| `static/src/js/cash_move_popup_patch.js` | Parche de `CashMovePopup`: muestra la confirmación y delega en el flujo estándar |
| `static/src/js/cash_move_confirm_popup.js` | Componente del diálogo (`Component` + `Dialog`) |
| `static/src/xml/cash_move_confirm_popup.xml` | Plantilla del diálogo |
| `static/src/css/cash_move_confirm_popup.css` | Diseño (auto-contenido bajo `.cash-move-confirm-popup`) |
| `models/pos_config.py` | Campos de configuración |
| `views/pos_config_views.xml` | Bloque de ajustes |
| `tests/test_cash_in_out_message.py` | 5 pruebas del cableado de configuración |

## Costuras que consume de `pos_closing_validation`

`isCashMoveBlocked()`, `isLastCashMove()`, `setLastMoveWarningSkipped()` y `state` del popup. Cambiar cualquiera de esos nombres obliga a actualizar este módulo en la misma tanda.

## Nota para futuras migraciones

Este módulo llegó de la 17 con los assets declarados bajo el nombre `cash_in_out_message`, que no existe como módulo: Odoo no fallaba el arranque, pero las entradas del bundle quedaban sin archivo y **el módulo no cargaba nada**. Al portar un módulo, conviene comprobar que cada entrada de `assets` apunte a `<nombre_de_carpeta>/static/...`.

## Licencia

LGPL-3

## Autor

Miguel Bolivar — Libertario Coffee
