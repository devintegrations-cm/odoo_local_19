# POS Closing Validation

Extensión del flujo de control de caja del Punto de Venta de **Odoo 19**.

Protege la integridad del efectivo con reglas de validación durante la operación y el cierre de sesiones. No reemplaza la contabilidad de Odoo: la complementa bloqueando operaciones inseguras antes de que ocurran, y **nunca deja una tienda sin poder cerrar su caja**.

---

## Funcionalidades

- **Límite configurable de movimientos de efectivo** (Cash In / Cash Out) por sesión.
- **Advertencia antes de consumir el último movimiento permitido.**
- **Movimientos idempotentes**: una petición reintentada (respuesta perdida o cola offline de Odoo) no duplica el movimiento.
- **Sesiones de rescate sin operación de caja**, reforzada en frontend y backend.
- **Bloqueo de aperturas nuevas** cuando existen sesiones de rescate pendientes (opt-in).
- **Snapshot unificado** anclado al balance teórico de Odoo: el número que validamos es el mismo que Odoo muestra.
- **Validación de diferencia autorizada** al cerrar (regla de negocio: aplica a todos los roles).
- **Cierre transaccional con bloqueo acotado** de fila: sin workers colgados ni terminales esperando indefinidamente.
- **Política por rol**: los chequeos de consistencia interna bloquean al cajero y advierten al responsable, con nota de auditoría.
- **Borrado de movimientos restringido a responsables** (Odoo 19 lo permitía a cualquier usuario con permisos contables).

---

## Requisitos

- Odoo 19.0
- `point_of_sale` instalado y configurado con un método de pago de efectivo con `is_cash_count`
- Python 3.10+

---

## Instalación

1. Copie `pos_closing_validation` en su carpeta de addons personalizados.
2. Actualice la lista de aplicaciones.
3. Busque **"Pos Closing Validation"** e instale.

Depende únicamente de `point_of_sale`.

### Upgrade desde la serie 17.x

- La **auditoría de continuidad de caja en apertura fue eliminada** (ver Regla 3 en el historial): el modelo de Odoo trata el saldo de apertura como un valor que el operador corrige, y una tienda puede legalmente empezar el día con otra base de caja por decisión ejecutiva. El campo `expected_opening_balance` ya no existe en el modelo; su columna en `pos_session` queda huérfana e inofensiva (puede eliminarla con `tools.drop_column` en una migración si la quiere limpia).
- `pos.config.cash_control` ahora es computado por Odoo a partir de los métodos de pago, por lo que el guard de "control de efectivo activado sin método de caja" se eliminó: en 19 ese estado es inalcanzable.
- Los términos traducibles de nivel de módulo usan `_lt` (traducción diferida); con `_` en tiempo de import Odoo 19 no detecta idioma y guarda la cadena sin traducir.

---

## Configuración

En **Ajustes → Punto de Venta** (y en cada POS individual):

| Campo | Descripción | Por defecto |
|-------|-------------|-------------|
| **Máximo de movimientos de efectivo** | Cash In/Out permitidos por sesión. | 2 |
| **Mensaje de diferencia de efectivo** | Texto propio para el bloqueo por diferencia; los importes se añaden al final. Vacío = mensaje por defecto. | vacío |
| **Validar sesiones de rescate** | Bloquea abrir una sesión nueva si hay rescates pendientes. | Falso |

La diferencia máxima autorizada reutiliza `set_maximum_difference` y `amount_authorized_diff` de Odoo: el cierre se bloquea cuando `|countado - esperado| > amount_authorized_diff`.

---

## Reglas de negocio

### Regla 1 — Apertura bloqueada por rescate pendiente

Con la validación activada, si el POS tiene una sesión `rescue=True` en estado distinto de `closed`, no se abre una sesión nueva. El mensaje indica el camino de resolución: el tablero del POS muestra el enlace de sesiones de rescate pendientes que abre la lista directamente (`open_opened_rescue_session_form`).

Se usa `UserError` y no `RedirectWarning` a propósito: `open_ui()` es llamado desde el controlador `/pos/ui`, que descarta su valor de retorno, así que una acción adjunta a la excepción nunca se renderizaría como botón.

### Regla 2 — Rescates no generan Cash In/Out

El frontend advierte y el backend lanza `UserError` con el mismo texto si se ignora la validación (RPC directo).

### Regla 3 — Snapshot único, reconciliado con Odoo

`expected_cash` es `cash_register_balance_end` de Odoo y `difference` es `cash_register_difference`. No se reimplementa la fórmula.

El desglose (`apertura + ventas + cash in − cash out`) se calcula con los mismos dominios de core (`_get_captured_payments_domain`, líneas de estado de cuenta de la sesión) para que cuadre contra ese total. Dos matices intencionados:

- **Ventas en efectivo** sólo cuentan pagos de pedidos capturados (`paid`/`invoiced`/`done`); los pagos de pedidos en `draft` o `cancel` no suman, igual que Odoo.
- **Cash In / Cash Out** del desglose incluyen *todas* las líneas de caja por signo (dinero real en el cajón), mientras que **el contador del límite** sólo cuenta las marcadas como movimiento del operador (`pos_cash_move`).

### Regla 4 — Límite de movimientos e idempotencia

El límite se comprueba tras tomar el bloqueo de fila y dentro de la misma transacción. El popup genera un `uuid` por movimiento en `extras['cash_move_uuid']`; el backend lo guarda en la línea y si recibe el mismo `uuid` dos veces no crea nada y responde éxito.

Esto importa porque Odoo 19 reintenta automáticamente los movimientos encolados (`data_service.execute` reenvía los mismos argumentos tras un fallo de conexión) y porque el cajero puede pulsar Confirmar de nuevo tras un error de red: sin la clave, ambos caminos exceden el límite en silencio.

### Regla 5 — Cierre transaccional con espera acotada

`post_closing_cash_details` adquiere el bloqueo de fila con `SET LOCAL lock_timeout` antes de validar, invalida el caché y valida contra datos frescos. En el camino de Cash In/Out el timeout es corto (2 s) porque esperar no aporta; en el cierre es mayor (10 s) porque conviene esperar y ver el estado real (`closing_control`) antes de responder.

Un `FOR UPDATE` sin acotar deja el worker HTTP colgado mientras el otro terminal publica el asiento de cierre; el 502 resultante no dice si el movimiento quedó registrado, que es exactamente como se duplica un movimiento. Al agotarse el timeout, el error incluye **el conteo actual** ("1 de 2") para que el operador no reintente a ciegas; el savepoint alrededor del bloqueo deja la transacción utilizable para esa lectura.

### Regla 6 — Consistencia de datos: cajero bloqueado, responsable advertido

Al cerrar se comprueban: órdenes pagadas sin pagos, pagos huérfanos (sólo posible en datos traídos de versiones anteriores), y movimientos que exceden el límite.

- **Cajero**: el cierre se bloquea con el mensaje correspondiente.
- **Responsable (`point_of_sale.group_pos_manager`)**: el cierre procede y se registra una nota en el chatter de la sesión con la regla saltada. Un falso positivo de una heurística interna no puede dejar una tienda con la caja abierta.

La regla monetaria (Regla de diferencia autorizada) **no** se suaviza: aplica a todos los roles.

### Regla 7 — Borrar un movimiento es cosa de responsables

En Odoo 19 el popup incluye lista de movimientos con borrado, y liberar un movimiento libera un cupo del límite. `delete_cash_in_out` exige `group_pos_manager` y el control de borrado se oculta en la lista para cajeros.

---

## Comportamiento sin conexión

| Situación | Comportamiento |
|-----------|----------------|
| Al abrir el popup de Cash In/Out | Banner de "sin conexión": el conteo se muestra desconocido, **no** bloqueado |
| Al confirmar el primer movimiento offline | Pedida confirmación explícita ("el límite se comprobará al sincronizar") |
| Movimientos offline | Se encolan por Odoo y se validan en servidor al sincronizar |
| Deriva de límites por movimientos offline | La atrapa la Regla 6 al cerrar, con la salida de responsable |
| Error del servidor que no sea desconexión (permisos, sesión borrada) | **Fail-closed**: el popup bloquea el confirm |

Es una decisión deliberada: negar el cajón a una tienda sin internet es peor que un límite temporalmente blando, porque el servidor sigue validando y el cierre auditaba la deriva.

---

## Errores comunes y qué hacer

**"La diferencia de efectivo supera la diferencia máxima autorizada"** — Pulsar **Cancelar** para volver a contar con el importe limpio, o **Revisar órdenes** si se sospecha de un pedido sin registrar. Si la diferencia es real, debe resolverla un responsable: esta regla no se salta con rol.

**"El Punto de Venta no está sincronizado con la sesión actual"** — El navegador muestra una sesión ya cerrada o es una rescate: recargar la página.

**"Se alcanzó el límite de movimientos de efectivo"** — No hay más movimientos en esta sesión. Para casos excepcionales, subir el límite o cerrar y abrir sesión nueva.

**"Existe una inconsistencia en los movimientos de efectivo"** — Hay más movimientos que el límite (típicamente tras bajarlo con una sesión activa). Un responsable puede cerrar y quedará registrado en el chatter; nunca baje el límite con sesiones activas.

**"No se pudo registrar el movimiento... Verifique ese conteo antes de reintentar"** — Otro terminal tiene el bloqueo de la caja (normalmente cerrando). El mensaje trae el conteo actual: compruebe que el movimiento no haya quedado ya registrado antes de repetirlo.

**"Solo un responsable del Punto de Venta puede eliminar un movimiento de efectivo"** — Registrar el movimiento compensatorio y avisar a un responsable.

---

## Flujo operativo

**Apertura:** Abrir sesión → (si hay rescate pendiente y la validación está activa, resolver desde el tablero) → ingresar saldo de apertura → confirmar.

**Operación:** Botón *Cash in/out*. Si es el último movimiento permitido, se pide confirmación explícita. Si no hay conexión, se avisa y se puede continuar.

**Cierre:** *Cerrar sesión* → el popup de Odoo muestra el desglose estándar y una fila adicional con **Movimientos de efectivo: X/N** → contar → confirmar. Se bloquea por diferencia excesiva, o por inconsistencia si quien cierra no es responsable.

#### Botones de los avisos de cierre

El manejo nativo de Odoo acompaña **cualquier** cierre fallido con un botón *Cancel Orders* que cancela todas las órdenes no finalizadas del terminal y reintenta el cierre. Es la salida correcta cuando quedan órdenes en borrador, y una pérdida de datos cuando el aviso dice "te faltó efectivo". Por eso cada respuesta de este módulo trae dos claves que el frontend respeta (`cash_validation`, `show_orders_action`), definidas junto a la regla que las genera:

| Aviso | Botones |
|-------|---------|
| Diferencia superada | **Revisar órdenes** · **Cancelar** (cierra el aviso, deja el contado en `0` y vuelve a contar) |
| Rescates pendientes | **Revisar órdenes** · **Cancelar** |
| Movimientos por encima del límite | **Entendido** |
| Orden pagada sin pago registrado | **Entendido** |
| Sesión de rescate / ya cerrada | **Entendido** |
| Avisos propios de Odoo (hay órdenes en borrador) | Sin cambios: conserva *Cancel Orders* |

Ninguna ruta de nuestros avisos cancela órdenes ni fuerza el cierre.

---

## Notas técnicas

### Campos

`pos.session`: `rescue_parent_session_id` (Many2one), `rescue_session_ids` (One2many inverso).
`pos.config`: `maximum_cash_in_out_moves`, `cash_difference_exceeded_message`, `enable_rescue_session_validation` (+ relacionados en `res.config.settings`).
`account.bank.statement.line`: `pos_cash_move` (Boolean, indexado), `pos_cash_move_uuid` (Char) con la restricción única `(pos_session_id, pos_cash_move_uuid)` declarada con `models.Constraint`. Ojo: el atributo `_sql_constraints` fue retirado en Odoo 19 y **se ignora dejando sólo un warning**, por lo que una restricción declarada así no llega a existir en la base de datos. Una violación llega al Python como `psycopg2.errors.UniqueViolation`, no como `UserError`.

### Endpoints expuestos al POS

| Método | Consumo | Notas |
|--------|---------|-------|
| `get_closing_validation_info` | Parche de `PosStore` (gates de caja y cierre) y fila del popup de cierre | Requiere `group_pos_user` |
| `get_cash_in_out_control_data` | Popup de Cash In/Out (auto-suficiente) | Requiere `group_pos_user` |

`get_closing_control_data` **no** se sobrecarga: añadir claves propias hace que OWL 2 rechace los props del popup estándar de cierre.

### Overrides sobre Odoo

`pos.session`: `try_cash_in_out`, `_prepare_account_bank_statement_line_vals`, `delete_cash_in_out`, `post_closing_cash_details`, `_cannot_close_session`, `_get_pending_rescue_sessions_for_config` (propio), `create`.
`pos.config`: `open_ui`, constraint de límite.

### Frontend (arquitectura de 19)

Popups y navbar viven en `point_of_sale/app/components/`; los puntos de entrada de caja son `PosStore.cashMove()` y `PosStore.closeSession()` (la plantilla del navbar ya no tiene métodos propios). No existe `AbstractAwaitablePopup` ni el servicio `popup`: se usan `ask()`/`makeAwaitable()` con `ConfirmationDialog`/`AlertDialog`.

| Archivo | Rol |
|---------|-----|
| `static/src/js/pos_store_patch.js` | Gates de caja y de cierre, alertas de recarga, snapshot cacheado en `pos.closingValidationInfo`, y los botones de los avisos de cierre (`handleClosingError`) |
| `static/src/js/cash_move_popup_patch.js` | Límite, aviso de último movimiento, clave de idempotencia, política offline |
| `static/src/js/cash_move_list_popup_patch.js` | Oculta el borrado a cajeros |
| `static/src/xml/cash_move_popup.xml` | Resumen, banners y botón confirmar fusionado con `isValidCashMove()` |
| `static/src/xml/closing_popup_extension.xml` | Fila de movimientos sobre `PaymentMethodBreakdown` |

### Costuras para `pos_cash_in_out_message`

Este módulo parcha `CashMovePopup`; el módulo del mensaje parcha el mismo componente y depende de que existan estas superficies estables:

- `pos.closingValidationInfo` — snapshot de la sesión (`is_manager`, desglose de caja) o `null`
- `getCashMoveControl()` → `{ count, limit }`, con `count === null` si no se pudo leer
- `isCashMoveBlocked()`, `isLastCashMove()` (alias legacy `_isLastMovement()`)
- `setLastMoveWarningSkipped(bool)` / `_skipCashMoveWarning`
- `state.isLimitReached`, `state.loadError`, `state.offline`
- `confirm()` encadenado por `super.confirm()`; el orden de parches lo garantiza `depends: ["pos_closing_validation"]`

Cambiar estas firmas obliga a actualizar `pos_cash_in_out_message` en la misma tanda.

### Pendiente de verificación en Odoo 19

**Odoo 19 no tiene ninguna ruta que cree sesiones de rescate.** `rescue` aparece en el campo (`readonly`, `copy=False`), en filtros de lectura y en mensajes, y el cliente todavía gestiona el reemplazo de sesión (`pos_store.js`), pero no se encontró código que escriba `rescue=True`. Regla 1, Regla 2, `rescue_parent_session_id` y el filtrado de rescates se migraron sin cambios y podrían ser inertes.

Para comprobarlo en una tienda real: abrir sesión en dos terminales, dejar un pedido sin sincronizar y cerrar desde la otra terminal; luego buscar sesiones "Recovery Session" en `Punto de Venta → Sesiones`. Si no aparecen, conviene recortar esta rama (~200 líneas del modelo y buena parte de los tests de rescate).

Un matiz relacionado: `rescue_parent_session_id` sólo se enlaza si `rescue` llega en los `vals` de `create`. Si una versión futura marca el rescate con un `write` posterior, el vínculo quedaría vacío y el rótulo "RESCATE DE …" desaparecería en silencio.

### Seguridad

Las reglas se aplican en el backend; el frontend sólo mejora la experiencia. Los endpoints de lectura exigen `group_pos_user` y las lecturas de `account.bank.statement.line` usan `sudo()` porque el cajero no tiene acceso a ese modelo (igual que hace core).

### Tests

59 tests en `tests/test_closing_validation.py`: snapshot y su invariante contra `cash_register_balance_end`, reconciliación del desglose, límite, idempotencia por `uuid`, contrato y fallo del bloqueo de fila, diferencia autorizada (todos los roles), cierre limpio, rescates, política de rol con nota de auditoría, borrado restringido, apertura bloqueada y validación de configuración.

La concurrencia real no es testeable en `TransactionCase`: los datos del test no están commiteados y `registry.cursor()` devuelve un `TestCursor` sobre la misma transacción, no una segunda conexión. Por eso se afirma el contrato SQL (timeout antes del `FOR UPDATE`) y se inyecta el fallo de bloqueo para verificar el mensaje accionable y que no se registra ningún movimiento.

---

## Licencia

LGPL-3

## Autor

Miguel Bolivar — Libertario Coffee
