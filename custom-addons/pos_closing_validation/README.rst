======================
Pos Closing Validation
======================

..
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! Generado por .claude/scripts/gen_readme.py          !!
   !! Los cambios se sobrescriben: editar readme/*.md     !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1| |badge2|

Refuerza el control de efectivo del Punto de Venta en dos momentos: durante la sesión, al registrar
**entradas y salidas de efectivo**, y al **cerrar la caja**.

Durante la sesión:

- Limita la cantidad de entradas/salidas de efectivo por sesión (por defecto, 2) y muestra en la
  ventana el contador de movimientos y un resumen del efectivo esperado.
- Avisa antes de registrar el **último movimiento permitido** y bloquea la ventana cuando el límite
  se alcanzó. El límite también se valida en el servidor.
- Evita que un reintento por corte de conexión registre dos veces el mismo movimiento.
- Solo un responsable del Punto de Venta puede eliminar un movimiento de efectivo.

Al cerrar la caja:

- Bloquea el cierre cuando la diferencia entre el efectivo contado y el esperado supera la
  **diferencia máxima autorizada** de Odoo, para cualquier rol, con un mensaje configurable.
- Revisa la consistencia de la sesión (movimientos por encima del límite, órdenes pagadas sin pagos,
  sesiones de rescate pendientes): bloquea al cajero y solo advierte al responsable, que puede
  cerrar dejando constancia en el historial de la sesión.
- Toma un bloqueo acotado sobre la sesión para que dos terminales no cierren ni muevan caja a la vez
  sin que ninguna quede colgada.

Opcionalmente, impide abrir una sesión nueva mientras existan sesiones de rescate sin cerrar.

**Table of contents**

.. contents::
   :local:

Installation
============

Dependencias
------------

- ``point_of_sale`` (Odoo 19 Community). No requiere otros módulos ni librerías de Python adicionales.
- El punto de venta necesita un método de pago de efectivo con **conteo de caja** (``is_cash_count``):
  el resumen de efectivo y la diferencia se calculan sobre ese método, igual que en Odoo.
- ``pos_cash_in_out_message``, de este mismo repositorio, depende de este módulo y usa sus avisos
  dentro de su diálogo de confirmación.

Pasos de instalación
--------------------

Instalar *Pos Closing Validation* desde *Aplicaciones*. El módulo agrega campos a la configuración
del punto de venta, a la sesión y a las líneas de extracto, y los archivos del POS. No crea menús
ni permisos nuevos. Después de instalar o actualizar, **volver a entrar al POS** desde el backend
para que cargue los archivos nuevos.

Migración desde Odoo 17
-----------------------

- Los campos de configuración conservan su nombre técnico (``maximum_cash_in_out_moves``,
  ``cash_difference_exceeded_message``, ``enable_rescue_session_validation``), por lo que la
  configuración existente se mantiene sin script de datos. Lo mismo vale para la marca
  ``pos_cash_move`` de los movimientos ya registrados.
- Se agrega la columna ``pos_cash_move_uuid`` con una restricción única por sesión. Los movimientos
  históricos quedan con el valor vacío, que no viola la restricción.
- Se eliminó la auditoría de continuidad del saldo de apertura de la 17 (campo
  ``expected_opening_balance`` y validación en ``set_cashbox_pos``). La columna queda huérfana en la
  base y no se usa.
- En Odoo 19 el control de efectivo del punto de venta se calcula a partir de los métodos de pago;
  la validación de la 17 que lo exigía junto con un método de caja ya no hace falta.

Configuration
=============

Ir a *Punto de venta › Configuración › Ajustes*, elegir el punto de venta en la parte superior y
buscar el bloque **Pagos**. Las opciones del módulo están junto a *Establecer la diferencia
máxima*, que es de Odoo.

.. figure:: ../static/description/01_configuracion.png
   :alt: Punto de venta › Configuración › Ajustes › Pagos: diferencia máxima de Odoo y las tres opciones del módulo

   Punto de venta › Configuración › Ajustes › Pagos: diferencia máxima de Odoo y las tres opciones del módulo

- **Establecer la diferencia máxima** y **Diferencia autorizada** (campos de Odoo
  ``set_maximum_difference`` y ``amount_authorized_diff``). Opcional; desmarcada por defecto. Es el
  interruptor de la validación de diferencia al cerrar: si está desmarcada, el módulo no compara el
  efectivo contado con el esperado.
- **Máximo de movimientos de efectivo** (``maximum_cash_in_out_moves`` de ``pos.config``).
  Obligatorio; 2 por defecto. Número de entradas/salidas de efectivo permitidas por sesión. Debe
  ser mayor que cero: el valor 0 o negativo se rechaza al guardar.
- **Mensaje de diferencia de efectivo** (``cash_difference_exceeded_message``). Opcional; vacío por
  defecto. Texto del aviso que bloquea el cierre por diferencia. Solo se escribe el texto: la
  diferencia y el máximo autorizado se agregan solos al final. Vacío, se usa el mensaje por defecto
  del módulo.
- **Validar sesiones de rescate** (``enable_rescue_session_validation``). Opcional; desmarcada por
  defecto. Impide abrir una sesión nueva mientras haya sesiones de rescate sin cerrar, y bloquea al
  cajero (advierte al responsable) al cerrar si hay rescates pendientes con datos.

A tener en cuenta:

- La configuración es **por punto de venta**. Hay que repetirla en cada tienda.
- El límite se lee del servidor cada vez que se abre la ventana de entrada/salida de efectivo, así
  que un cambio en el límite rige desde el siguiente movimiento, sin volver a entrar al POS.
- **No bajar el límite con sesiones abiertas.** Si una sesión ya tiene más movimientos que el nuevo
  límite, el cajero no podrá cerrarla (ver *Solución de problemas*).
- La diferencia de efectivo se valida para todos los roles, incluidos los responsables.
- Quién es "responsable" se decide por el grupo de administrador del Punto de Venta
  (``point_of_sale.group_pos_manager``) del **usuario de Odoo** con el que se abrió el POS. El
  empleado elegido con PIN en ``pos_hr`` no cambia ese rol.

Usage
=====

Entradas y salidas de efectivo
------------------------------

En el POS, abrir el menú (☰) y elegir **Entrada/salida de efectivo**. Antes de abrir la ventana,
el POS consulta el estado de la sesión en el servidor. La ventana muestra, además de los campos de
Odoo, un **resumen de efectivo** (apertura, ventas en efectivo, entradas, salidas y efectivo
esperado) y el **contador** de movimientos de la sesión frente al máximo configurado.

.. figure:: ../static/description/02_movimiento_contador.png
   :alt: Ventana de entrada/salida de efectivo con el resumen y el contador de movimientos

   Ventana de entrada/salida de efectivo con el resumen y el contador de movimientos

Si el movimiento que se va a registrar es el último permitido, se pide una confirmación explícita.
Con ``pos_cash_in_out_message`` instalado, el aviso aparece dentro de su diálogo de confirmación
(captura); sin ese módulo, aparece un diálogo propio, *Último movimiento de efectivo*, con el
conteo y los botones *Confirmar* y *Cancelar*.

.. figure:: ../static/description/03_ultimo_movimiento.png
   :alt: Aviso de último movimiento permitido dentro del diálogo de confirmación

   Aviso de último movimiento permitido dentro del diálogo de confirmación

Cuando la sesión ya usó todos los movimientos, la ventana muestra **Límite alcanzado** y el botón
*Confirmar* queda deshabilitado. Si el aviso se saltara (por ejemplo, con una llamada directa al
servidor), el servidor rechaza el movimiento con *Se alcanzó el límite de movimientos de efectivo*.

.. figure:: ../static/description/04_limite_alcanzado.png
   :alt: Ventana bloqueada por límite alcanzado: aviso, contador en el máximo y Confirmar deshabilitado

   Ventana bloqueada por límite alcanzado: aviso, contador en el máximo y Confirmar deshabilitado

Cierre de caja
--------------

Al elegir **Cerrar caja registradora**, el POS consulta primero el estado de la sesión. Si el
usuario no puede cerrar, aparece *No se puede cerrar la sesión* con los motivos, y la ventana de
cierre de Odoo no llega a abrirse. Si puede, se abre la ventana de cierre estándar. Al confirmar,
el servidor valida de nuevo y, si algo falla, muestra el aviso con estos botones:

- **Diferencia superada** (el efectivo contado se aparta del esperado más que la diferencia
  autorizada): *Revisar órdenes*, que lleva a la lista de órdenes, o *Cancelar*, que deja el
  efectivo contado en 0 para volver a contar. Aplica a todos los roles.
- **Sesiones de rescate pendientes**: *Revisar órdenes* o *Cancelar*.
- **Movimientos por encima del límite** u **órdenes pagadas sin pagos**: un único botón,
  *Entendido*.

Ningún aviso del módulo cancela órdenes. El botón de Odoo que cancela las órdenes abiertas se
mantiene solo para los avisos propios de Odoo (por ejemplo, órdenes en borrador).

Casos especiales
----------------

- **Responsable del Punto de Venta**: las revisiones de consistencia (movimientos por encima del
  límite, órdenes pagadas sin pagos, rescates pendientes) no lo bloquean. Si cierra con alguna
  activa, queda una nota *Validación de caja superada por un responsable* en el historial de la
  sesión. La diferencia autorizada sí lo bloquea.
- **Quién ve el aviso de diferencia**: la ventana de cierre de Odoo ya compara el conteo con la
  diferencia autorizada. A un usuario que no es responsable, Odoo le muestra su propio aviso y no
  lo deja continuar; a un responsable le ofrece seguir de todos modos. En ese caso el servidor
  aplica la regla del módulo y el cierre se bloquea igual.
- **Sin conexión**: la ventana avisa que no puede verificar el límite y pide confirmar *Registrar
  de todos modos*. El movimiento queda en la cola del POS y el servidor aplica el límite al
  sincronizar. Si el servidor responde con un error que no es de conexión, la ventana se bloquea.
- **Reintentos**: cada ventana genera un identificador único para su movimiento. Si el POS reenvía
  el mismo movimiento (respuesta perdida o cola sin conexión), el servidor lo reconoce y no lo
  registra dos veces.
- **Dos terminales a la vez**: el movimiento de efectivo espera hasta 2 segundos a que la otra
  terminal libere la sesión, y el cierre hasta 10 segundos. Si se agota la espera, el aviso trae el
  conteo actual de movimientos para comprobarlo antes de reintentar.
- **Sesión de rescate**: no admite movimientos de efectivo ni se cierra desde el POS; se cierra
  desde el backend.
- **Eliminar un movimiento**: el servidor solo lo permite a un responsable del Punto de Venta.

Solución de problemas
---------------------

- **"Se alcanzó el límite de movimientos de efectivo"**: la sesión no admite más movimientos. Para
  un caso excepcional, un responsable puede subir el límite en Ajustes; rige desde el siguiente
  movimiento.
- **"Existe una inconsistencia en los movimientos de efectivo"**: la sesión tiene más movimientos
  que el límite, normalmente porque el límite se bajó con la sesión abierta o por movimientos
  sincronizados después de un corte. Un responsable puede cerrar la sesión; queda registrado en el
  historial.
- **"La diferencia de efectivo supera la diferencia máxima autorizada"** (o el mensaje
  configurado): volver a contar con *Cancelar*, o revisar si falta registrar una orden. Si la
  diferencia es real, la regla no se salta con un rol: hay que corregir el conteo o ajustar la
  diferencia autorizada.
- **"Hay N órdenes pagadas sin pagos registrados"**: una orden pagada con total distinto de cero
  no tiene líneas de pago. Revisarla antes de cerrar o pedir a un responsable que cierre.
- **"No se pudo registrar el movimiento... Otro terminal está utilizando la caja"**: otra terminal
  está cerrando o moviendo caja. Comprobar el conteo que trae el mensaje antes de repetir el
  movimiento.
- **"El Punto de Venta no está sincronizado con la sesión actual"** o **"Sesión no disponible"**:
  el navegador tiene una sesión cerrada o de rescate. Pulsar *Actualizar la página*.
- **"No puede abrir una nueva sesión porque existe(n) sesión(es) de rescate pendiente(s)"**: abrir
  el tablero del punto de venta, entrar al enlace de sesiones de rescate pendientes y cerrarlas.
- **"Solo un responsable del Punto de Venta puede eliminar un movimiento de efectivo"**: registrar
  el movimiento contrario y avisar a un responsable.

Known issues / Roadmap
======================

Limitaciones conocidas
----------------------

- **La fila "Movimientos de efectivo X/N" no aparece en la ventana de cierre si el punto de venta
  usa ``pos_hr``.** ``closing_popup_extension.xml`` la inserta después del desglose de entradas/salidas
  del bloque estándar, pero con ``pos_hr`` activo en el punto de venta Odoo oculta ese bloque y dibuja
  una copia propia. Comprobado en el POS local, que tiene ``pos_hr`` activo: la plantilla heredada
  contiene la fila, pero no se muestra. Por eso no hay captura de la ventana de cierre. Verificar en
  STG qué tiendas tienen ``pos_hr`` activo.
- **La lista de movimientos no se puede abrir desde el POS.** ``cash_move_popup.xml`` elimina el
  botón *Detalles* de la ventana de entrada/salida de efectivo, y en Odoo 19 esa lista solo se abre
  desde ese botón. En consecuencia, ``cash_move_list_popup_patch.js``, que oculta el borrado a los
  cajeros, no tiene efecto visible. La restricción de borrado sigue aplicándose en el servidor.
- **Las sesiones de rescate pueden no existir en Odoo 19.** El core de Odoo 19 conserva el campo
  ``rescue`` y lo filtra, pero no se encontró código fuera de los tests que cree una sesión con
  ``rescue=True``. La validación de apertura, el bloqueo de movimientos en rescates y el enlace
  ``rescue_parent_session_id`` se migraron sin cambios y podrían no activarse nunca. Para comprobarlo
  en una tienda: buscar sesiones de rescate en *Punto de venta › Sesiones* después de operar.
- ``rescue_parent_session_id`` solo se completa si ``rescue`` llega en los valores de creación de la
  sesión; si una versión futura marca el rescate con una escritura posterior, el vínculo queda
  vacío.
- El rol de responsable sale del usuario de Odoo, no del empleado de ``pos_hr``. En una tienda donde
  todos los empleados comparten un usuario con permisos de administrador del POS, las revisiones de
  consistencia nunca bloquean.
- Los campos nuevos de la sesión (``rescue_parent_session_id``, ``rescue_session_ids``) y de las líneas
  de extracto (``pos_cash_move``, ``pos_cash_move_uuid``) no se muestran en ninguna vista.
- Falta ``static/description/icon.png``: en *Aplicaciones* se ve el ícono genérico de Odoo.

Componentes
-----------

- ``models/pos_config.py``: los tres campos de ``pos.config``, sus relacionados con prefijo ``pos_`` en
  ``res.config.settings``, la restricción del límite mayor que cero y el bloqueo de apertura por
  rescates pendientes (``open_ui`` → ``_check_rescue_sessions_before_open_ui``). Se usa ``UserError`` y no
  ``RedirectWarning`` porque el controlador ``/pos/ui`` descarta el valor de retorno de ``open_ui()``.
- ``models/pos_session.py``: límite e idempotencia (``try_cash_in_out``,
  ``_prepare_account_bank_statement_line_vals``), borrado solo para responsables
  (``delete_cash_in_out``), bloqueo acotado de la fila de la sesión (``_lock_session_row``, 2 s para
  movimientos y 10 s para el cierre), validaciones de cierre (``_cannot_close_session``,
  ``post_closing_cash_details``, ``_check_authorized_cash_difference``) y los dos endpoints del POS,
  ``get_cash_in_out_control_data`` y ``get_closing_validation_info``, que exigen el grupo de usuario del
  POS.
- ``models/account_bank_statement_line.py``: la marca ``pos_cash_move`` y el identificador
  ``pos_cash_move_uuid``, con restricción única por sesión declarada con ``models.Constraint``.
- ``views/pos_config_views.xml``: las tres opciones en *Ajustes › Pagos*, después de *Establecer la
  diferencia máxima*.
- ``static/src/js/pos_store_patch.js``: controles previos a *Entrada/salida de efectivo* y a *Cerrar
  caja registradora*, y los botones de los avisos de cierre (``handleClosingError``).
- ``static/src/js/cash_move_popup_patch.js`` y ``static/src/xml/cash_move_popup.xml``: contador,
  resumen, aviso de último movimiento, bloqueo por límite, avisos sin conexión y el identificador
  del movimiento.
- ``static/src/js/cash_move_list_popup_patch.js``: oculta el borrado a quien no es responsable (ver
  *Limitaciones conocidas*).
- ``static/src/xml/closing_popup_extension.xml``: la fila de movimientos en la ventana de cierre (ver
  *Limitaciones conocidas*).

Notas para mantenimiento
------------------------

- **Contrato con ``pos_cash_in_out_message``.** Ese módulo parcha el mismo ``CashMovePopup`` y usa
  ``isCashMoveBlocked()``, ``isLastCashMove()``, ``setLastMoveWarningSkipped()``, ``getCashMoveControl()``,
  ``pos.closingValidationInfo`` y ``confirm()`` encadenado con ``super``. Renombrar cualquiera obliga a
  cambiar los dos módulos en el mismo commit.
- **Todas las reglas se deciden en el servidor**; el POS solo las muestra. Un aviso quitado del JS
  no habilita nada que el servidor rechace.
- ``get_closing_control_data`` de Odoo no se sobreescribe a propósito: agregar claves a su respuesta
  hace que OWL rechace las props de la ventana de cierre estándar.
- El resumen usa los cálculos de Odoo: el efectivo esperado es ``cash_register_balance_end`` y la
  diferencia es ``cash_register_difference``. Las entradas/salidas del resumen suman todas las líneas
  de caja de la sesión por signo; el contador del límite solo cuenta las marcadas con
  ``pos_cash_move``.
- Las cadenas de nivel de módulo usan ``_lt``: con ``_`` en tiempo de importación Odoo 19 no detecta el
  idioma y guarda el texto sin traducir.
- **Tests.** ``tests/test_closing_validation.py`` tiene 66 tests: resumen y su igualdad con
  ``cash_register_balance_end``, límite, idempotencia, contrato del bloqueo acotado, diferencia
  autorizada para todos los roles, política por rol con nota de auditoría, borrado restringido,
  rescates y apertura bloqueada. La concurrencia real no se puede probar en ``TransactionCase``: se
  prueba el contrato SQL y se simula el fallo del bloqueo. El JS del POS no tiene tests
  automáticos.
- Los comentarios de ``_filter_non_empty_rescues`` y ``create`` en ``pos_session.py`` remiten al
  ``README.md`` anterior; ese contenido está ahora en *Limitaciones conocidas*.

Credits
=======

Authors
-------

- Miguel Bolivar
- Libertario Coffee

Contributors
------------

- Miguel Bolivar
