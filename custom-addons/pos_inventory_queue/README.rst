===================
Pos Inventory Queue
===================

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

Saca la validación de inventario de las ventas del Punto de Venta fuera de la petición del cajero y
la procesa en una **cola persistente**, un picking a la vez por producto. Así varias cajas pueden
vender el mismo producto al mismo tiempo sin chocar en la base de datos.

Sin el módulo, con inventario **en tiempo real**, cada venta valida su picking (``_action_done()``)
dentro de la misma petición que registra la orden. Cuando dos cajas tocan el mismo producto a la
vez, PostgreSQL devuelve errores de serialización o de bloqueo; además, el core de Odoo atrapa los
``UserError``/``ValidationError`` de esa validación y los descarta en silencio, y el picking queda sin
validar.

Con el módulo, la venta solo **crea** el picking y deja un ítem ``pending`` en la cola, en la misma
transacción de la orden. El worker de cron valida después cada picking, con bloqueos por producto y
compañía, reintentos y registro del error si falla. Los fallos quedan a la vista en
*Punto de venta › Órdenes › Cola de Inventario*, y la sesión no se puede cerrar mientras quede
inventario sin validar.

La cola se enciende y apaga con un **interruptor global**, activado por defecto.

**Table of contents**

.. contents::
   :local:

Installation
============

Dependencias
------------

- ``point_of_sale`` (Odoo 19 Community). No hay dependencias externas ni librerías de Python
  adicionales.

Pasos de instalación
--------------------

Instalar el módulo desde *Aplicaciones*. Crea el modelo de la cola, su secuencia (``PIQ/000001``),
dos acciones planificadas, el parámetro del sistema ``pos_inventory_queue.enabled`` con valor ``True``
y los menús *Órdenes › Cola de Inventario* y *Configuración › Inventario (Queue)*. Desde ese momento
la cola queda activa: no hace falta configurar nada más para que funcione.

El procesamiento depende de las acciones planificadas, así que el servidor tiene que correr con el
planificador de tareas habilitado (workers de cron).

Migración desde Odoo 17
-----------------------

El módulo conserva el mismo nombre técnico y los mismos campos que en 17. Al actualizar desde la
versión ``17.0.1.2.1`` se ejecuta ``migrations/17.0.2.1.0/pre-migrate.py``, que agrega la columna
``next_retry_date`` a ``pos_inventory_queue`` solo si no existe; se puede ejecutar más de una vez sin
efecto. Los datos de acciones planificadas, secuencia y parámetro están en ``noupdate="1"``: una
actualización no pisa el valor del interruptor ni los cambios hechos a los cron.

Respecto de 17 se retiraron tres piezas: el bloqueo de numeración de facturas
(``account_move._set_next_sequence``, que en Odoo 19 ya resuelve el core), el pool de conexiones
propio (ahora el drenaje corre en el worker de cron) y la vista en *Ajustes*, que en 17 no estaba
cargada en el manifiesto. Se agregaron la guarda de cierre de sesión, el reintento diferido
(``next_retry_date``) y la alerta de fallo permanente.

Configuration
=============

Ir a *Punto de venta › Configuración › Inventario (Queue)*. Se abre una ventana con un único
interruptor.

.. figure:: ../static/description/01_menu_configuracion.png
   :alt: Punto de venta › Configuración: menú Inventario (Queue)

   Punto de venta › Configuración: menú Inventario (Queue)

.. figure:: ../static/description/02_configuracion.png
   :alt: Ventana Inventory Queue: interruptor POS Inventory Queue y botón Guardar

   Ventana Inventory Queue: interruptor POS Inventory Queue y botón Guardar

- **POS Inventory Queue** (parámetro del sistema ``pos_inventory_queue.enabled``). Opcional;
  **activado** por defecto, y si el parámetro no existe el código también lo toma como activado.
  Activado, las ventas crean el picking y lo encolan. Desactivado, cada venta valida su picking en
  el momento, como Odoo estándar, y no se crean ítems nuevos. Los ítems que ya estaban en la cola
  se siguen procesando igual: el procesador drena siempre, esté o no activado.
- El valor se guarda con **Guardar**. *Descartar* cierra la ventana sin cambios.

A tener en cuenta:

- **Es global.** No depende del punto de venta ni de la compañía: afecta a todas las cajas.
- **Solo un administrador puede cambiarlo.** Según ``security/ir.model.access.csv``, el grupo
  *Administración / Ajustes* tiene todos los permisos sobre esta ventana; el *Administrador* del
  Punto de venta solo puede leerla.
- **Condición previa: inventario en tiempo real.** La cola solo interviene cuando la orden genera
  su picking en el momento. Eso depende del ajuste estándar *Gestión de inventario* de la compañía
  (en *Punto de venta › Configuración › Ajustes*, bloque *Inventario*, visible solo en modo
  desarrollador), que en Odoo 19 viene en *En tiempo real*. Con *Al cierre de
  la sesión* la cola no actúa, salvo en los casos que el core fuerza en tiempo real: contabilidad
  anglosajona con la orden facturada, o devolución de una orden de envío posterior.
- **Acciones planificadas** (*Ajustes › Técnico › Acciones planificadas*, en modo desarrollador):
  *POS Inventory Queue: Process pending items* corre **cada 1 minuto** y es la red de seguridad del
  drenaje; *POS Inventory Queue: Cleanup done items* corre **cada 7 días** y borra los ítems ``done``
  con más de 30 días. No hay que tocarlas; si se desactiva la primera, la cola solo avanza cuando
  una venta o un botón dispara el cron.

Usage
=====

Flujo
-----

El cajero no hace nada distinto: vende y cobra como siempre. Lo que cambia ocurre en el servidor:

- Al registrar la orden, el módulo crea el picking **en borrador**, sin reservar stock ni validarlo,
  y un ítem de cola en estado *Pending* con referencia ``PIQ/000NNN`` que guarda las líneas de la
  venta. Así la venta no toca el stock y no compite con las otras cajas. Si la venta tiene
  productos a entregar y devueltos, crea un picking y un ítem para cada parte.
- En la misma transacción pide al worker de cron que drene la cola. Si ese aviso se pierde, la
  acción planificada de cada minuto lo retoma.
- El worker toma los ítems de a uno, primero los *Pending*. Confirma el picking, reserva el stock,
  asigna cantidades, lotes y series desde las líneas de la venta, lo valida y marca el ítem *Done*.
  Cuando la cola se vacía, termina. En *Inventario* el picking se ve unos segundos en *Borrador*
  hasta que la cola lo procesa.

Para ver la cola, ir a *Punto de venta › Órdenes › Cola de Inventario*. Abre con el filtro
**Pendientes + Fallidos**, que muestra solo lo que necesita atención; si la lista está vacía, no hay
nada atrasado.

.. figure:: ../static/description/03_cola_de_inventario.png
   :alt: Punto de venta › Órdenes › Cola de Inventario, con el filtro por defecto (la fila es el ejemplo DOC)

   Punto de venta › Órdenes › Cola de Inventario, con el filtro por defecto (la fila es el ejemplo DOC)

Quitando el filtro, o eligiendo *Done*, se ven los ítems procesados. El color de la fila indica el
estado.

.. figure:: ../static/description/04_cola_procesados.png
   :alt: Lista de la cola con el filtro Done

   Lista de la cola con el filtro Done

.. figure:: ../static/description/06_item_procesado.png
   :alt: Ítem procesado: estado Done, picking y orden del POS de origen

   Ítem procesado: estado Done, picking y orden del POS de origen

Estados
-------

- **Pending** (azul): esperando turno.
- **Processing** (amarillo): un worker lo tomó. Si queda así más de 5 minutos, porque el worker
  murió o se cortó la conexión, la cola lo vuelve a tomar.
- **Done** (verde): picking validado. Se borra automáticamente a los 30 días.
- **Failed** (rojo): la validación dio un error de lógica, por ejemplo un producto con lote o serie
  sin asignar. Se reintenta solo, esperando 2, 4, 8 y 16 minutos entre intentos; *Next Retry*
  indica cuándo.
- **Failed Permanent** (rojo): falló en 5 ciclos seguidos. Ya no se reintenta solo.

Qué hacer con un ítem fallido
-----------------------------

Abrir el ítem desde la lista. La sección *Error* muestra la excepción y la traza, y *Retry Count*
cuántos ciclos lleva. Corregir la causa en el picking o en el producto y pulsar **Retry**.

.. figure:: ../static/description/05_item_fallido.png
   :alt: Ítem PIQ/002889 en Failed Permanent tras 5 ciclos: venta de un producto con lote sin lote asignado, con los botones Retry y Procesar ahora

   Ítem PIQ/002889 en Failed Permanent tras 5 ciclos: venta de un producto con lote sin lote asignado, con los botones Retry y Procesar ahora

- **Retry** (solo *Administrador* del Punto de venta, visible en *Failed* y *Failed Permanent*):
  vuelve el ítem a *Pending*, borra el error, pone el contador en 0 y avisa al cron.
- **Procesar ahora** (solo *Administrador* del Punto de venta): no procesa nada en el navegador.
  Pide al cron que drene la cola y muestra el aviso "Procesamiento solicitado".

Casos especiales
----------------

- **Errores de inventario.** Un problema de lote, serie o unidad de medida ya no hace fallar la
  venta en el POS: la venta entra y el error aparece en la cola (*Failed*, con reintentos y, si
  persiste, la alerta a los gestores de inventario).
- **PDF de la factura.** Las ventas facturadas se confirman sin generar el PDF dentro; el PDF se
  genera justo después, antes de que el POS reciba la respuesta, así que el POS ve la factura con su
  PDF igual que antes. Mientras tanto el número de factura queda libre para las otras ventas del
  mismo diario. Si la generación falla, la factura queda publicada y la completa la acción
  planificada de Odoo *Send invoices automatically* (debe estar activa). Para volver a generar el
  PDF dentro de la venta: parámetro de sistema ``pos_inventory_queue.invoice_pdf_after_commit`` en
  ``False``.
- **Volver a reservar en la venta.** El parámetro de sistema ``pos_inventory_queue.defer_reservation``
  (por defecto ``True``) activa la reserva en la cola. En ``False`` la venta vuelve a confirmar y
  reservar el picking como antes y la cola solo lo valida; aplica a las ventas nuevas, y los
  pickings en borrador que ya estén en cola se completan igual.

- **Contención con otra caja.** Si el intento choca con otro proceso sobre el mismo stock (error
  de serialización o ``lock_not_available``), se reintenta hasta 5 veces con esperas cortas, de hasta
  0,8 segundos. Si sigue chocando, el ítem vuelve a *Pending* sin sumar ciclos de fallo, y queda
  el detalle en *Error Message*.
- **Picking ya validado.** Si al tomar el ítem el picking ya está *Hecho*, lo marca *Done* sin
  volver a validar, para no descontar stock dos veces, y le recalcula el costo de la orden.
- **Costo y margen de la orden.** El costo de los productos con método FIFO o AVCO sale de los
  movimientos del picking, así que se calcula recién cuando la cola lo valida (si no, quedaría en 0
  y el margen de la orden, mal). Los productos de costo estándar no se tocan: su costo sale de la
  tarifa del producto y es el mismo validando la cola o no.
- **Líneas sin stock.** Servicios y cantidades en cero no generan picking ni ítem.
- **Devolución total de una orden cuyo picking aún no se validó.** Se cancela el picking original y
  no se crea ninguno nuevo. En una devolución parcial se reducen las cantidades del picking
  pendiente.
- **Cola apagada con ítems pendientes.** Los pendientes se terminan de procesar; las ventas nuevas
  se validan en el momento.
- **Cierre de sesión.** Antes de cerrar, Odoo procesa en línea todos los ítems de esa sesión que
  no estén *Done*, incluidos los fallidos: si su causa ya se resolvió (por ejemplo, alguien validó
  el picking a mano), el cierre los marca *Done* solo. Si después queda alguno sin *Done*, el
  cierre se detiene con el mensaje "No se puede cerrar la sesión … quedan N movimiento(s) de
  inventario sin procesar en la cola" y la lista de referencias.
- **Fallo permanente.** El log registra una línea con el prefijo ``POS Queue: PERMANENT``. Además,
  el sistema crea una actividad **To Do** para cada gestor de inventario de la compañía del
  picking, con el picking como referencia, visible en *Actividades* del systray. Se crea una sola
  vez por picking: los reintentos posteriores no la duplican. Para revisar la causa, abrir el
  picking o el ítem de la cola en *Punto de venta › Órdenes › Cola de Inventario*. La nota de la
  actividad dice *Punto de Venta › Configuración › Cola de Inventario*, pero la cola está en
  *Órdenes*.

.. figure:: ../static/description/07_alerta_picking.png
   :alt: Picking WH/POS/03049 con la actividad To Do de fallo permanente, que también aparece en Actividades del systray

   Picking WH/POS/03049 con la actividad To Do de fallo permanente, que también aparece en Actividades del systray

- **Numeración de ventas del POS.** Las secuencias de órdenes, líneas y referencia backend de cada
  POS usan la implementación *Estándar*, como en Odoo 17, en lugar de *Sin espacio* (la que crea
  Odoo 19, que hace esperar a los cajeros de una misma tienda). Los POS nuevos nacen así y los
  existentes se convierten al actualizar el módulo, sin saltos en la numeración. Para verificarlo,
  en modo desarrollador: *Ajustes › Técnico › Secuencias*, buscar el nombre del POS y abrir *Orden
  de PdV…*, *Línea de la orden de PdV…* y *Backend de la orden de PdV…*: las tres deben decir
  *Estándar*. *Dispositivo de PdV…* queda en *Sin espacio*: no se usa al vender. No es numeración
  fiscal: la factura electrónica numera con su propio diario.

.. figure:: ../static/description/08_secuencia_standard.png
   :alt: Ajustes › Técnico › Secuencias › Orden de PdV de la configuración #1: Implementación Estándar

   Ajustes › Técnico › Secuencias › Orden de PdV de la configuración #1: Implementación Estándar

Solución de problemas
---------------------

- **La sesión no cierra por movimientos sin procesar.** Filtrar la cola por la orden o el picking
  que indica el mensaje. Si el ítem está en *Failed* o *Failed Permanent*, corregir la causa y
  pulsar *Retry* (o intentar cerrar de nuevo: el propio cierre reintenta los ítems fallidos). Si
  el picking ya está *Hecho* pero el ítem no, basta con volver a intentar el cierre: la cola lo
  marca *Done* sin revalidar, ni siquiera hace falta *Retry*. El mensaje menciona *Punto de Venta ›
  Configuración › Cola de Inventario*, pero la cola está en *Órdenes*.
- **Ítems en *Pending* que no avanzan.** Revisar que la acción planificada *POS Inventory Queue:
  Process pending items* esté activa y que el servidor tenga workers de cron. En el log, cada
  pasada deja una línea ``POS Queue: summary reason=... elapsed=... done=N contention=N failed=N permanent=N``.
- **Ítem en *Processing* por mucho tiempo.** Pasados 5 minutos la cola lo vuelve a tomar sola. Si
  no ocurre, es el mismo caso del punto anterior: el cron no está corriendo.
- **El stock de una venta tarda en reflejarse.** Es lo esperado: el descuento ocurre cuando el
  worker procesa el ítem, normalmente en segundos. Para ver el stock en el momento, apagar la cola.
- **Qué dice el error.** *Error Message* guarda el tipo de excepción, el código SQLSTATE si lo hay
  y la traza, recortados a 4000 caracteres.

Known issues / Roadmap
======================

Limitaciones conocidas
----------------------

- **Cliente repetido en las facturas.** Con ``auth_signup.invitation_scope = b2c`` (así está
  producción), publicar cada factura escribe en la ficha del cliente (``auth_signup`` ›
  ``signup_prepare``) si no tiene usuario y recibe la notificación. Si todas las tiendas le facturan
  al mismo cliente ("Consumidor final"), esas ventas chocan en esa fila. Es configuración, no del
  módulo; verificar en producción qué clientes concentran la facturación.
- **Devolución parcial de un producto con lote mientras su picking sigue en cola.** Se reduce la
  demanda del move, pero la cola asigna el lote según la cantidad de la línea original. Es una
  ventana de segundos; mismo comportamiento que tenía la reserva en la venta.

- **La cola solo actúa con stock "En tiempo real".** Si la compañía tiene *Actualizar cantidades
  en stock* = *Al cierre de la sesión*, las ventas del POS no crean picking (Odoo arma uno solo al
  cerrar) y la cola no interviene, salvo en ventas facturadas con contabilidad anglosajona
  (``pos.order._force_create_picking_real_time``). La base local está así; hay que confirmar la
  configuración de producción. La opción se copia a cada sesión al abrirla
  (``pos.session.update_stock_at_closing``), así que un cambio solo aplica a sesiones nuevas.
- **Presupuesto de tiempo del drenaje.** ``_process_queue`` corre hasta 240 segundos por pasada. Si
  el límite real de los cron del servidor (``limit_time_real_cron``) es menor, el worker puede morir
  antes y dejar un ítem en *Processing* hasta el reclamo de 5 minutos (PIQ-6, verificar en
  producción).
- **Un solo drenador en la operación normal.** Odoo no corre el mismo cron dos veces en paralelo,
  así que fuera de los cierres de caja la cola la procesa un único drenador. Localmente validó 60
  pickings de una línea a ~15 por segundo; con órdenes reales de varias líneas y la base de
  producción hay que medirlo en staging antes de crecer a 100 tiendas. Si no alcanza, las
  opciones son varios crons repartiéndose la cola (ya es seguro con los locks de sesión) y un
  lock por ubicación además de producto.
- **El lock de stock no distingue tiendas.** La clave es (producto, compañía): dos tiendas que
  venden el mismo producto se esperan entre sí aunque sus quants estén en ubicaciones distintas. El
  comentario del código lo justifica con ``stock_valuation_layer``, tabla que ya no existe en Odoo 19;
  falta verificar qué comparten de verdad las tiendas en la valoración de 19 antes de cambiarlo.
- **Rutas equivocadas en los mensajes.** El error de cierre de sesión y la nota de la alerta dicen
  *Punto de Venta › Configuración › Cola de Inventario*; el menú real es *Órdenes › Cola de
  Inventario*.
- **Código sin efecto visible.** ``pos.session.queue_pending_count`` y ``action_view_queue_items`` no
  aparecen en ninguna vista. El override de ``stock.move._get_related_invoices`` no tiene llamador en
  el fuente de Odoo 19 Community (solo lo extienden ``sale_stock`` y ``purchase_stock``), y su
  comentario menciona ``stock_valuation_layer``, que ya no existe en 19.
- **Limpieza por borrado.** La ayuda del campo ``active`` dice que los ítems se archivan, pero la
  limpieza semanal los borra (``unlink``). El filtro *Archived* de la búsqueda solo encuentra ítems
  archivados a mano.
- **Textos mezclados.** Las etiquetas de los campos, estados y filtros están en inglés sin
  traducción (*Pending*, *Retry*, *Done*); los mensajes al usuario y el menú, en español.
- Falta ``static/description/icon.png``: en *Aplicaciones* se ve el ícono genérico de Odoo.

Componentes
-----------

- ``models/inventory_queue.py``: el modelo ``pos.inventory.queue``. Reclamo de ítems, procesamiento
  en cursor aparte, bloqueos, reintentos, disparo del cron, alerta, recálculo del costo de la
  orden al validar el picking, botones y limpieza. Constantes: ``MAX_RETRIES = 5``,
  ``CLAIM_MAX_RETRIES = 10``, ``STALE_PROCESSING_MINUTES = 5``, ``LOCK_TIMEOUT_SECONDS = 5``.
- ``models/inventory_queue_config.py``: la ventana del interruptor (``pos.inventory.queue.config``,
  transitorio), que lee y escribe ``pos_inventory_queue.enabled``.
- ``models/pos_order.py``: ``_create_order_picking`` llama al método del core con el contexto
  ``pos_inventory_queue=True``, que es lo que activa la cola; y ``_recompute_cost_after_queue``, que recalcula el costo FIFO/AVCO de
  la orden cuando la cola valida el picking (ver *Casos especiales* en *Uso*).
- ``models/pos_order.py`` (factura): ``_generate_pos_order_invoice`` factura sin PDF y lo agenda en un
  post-commit (``_pos_queue_schedule_invoice_pdf``); ``_pos_queue_generate_invoice_pdf_isolated`` lo
  genera en su propia transacción y, si falla, ``_pos_queue_invoice_pdf_fallback`` deja la factura al
  cron nativo de envío.
- ``models/stock_picking.py``: ``_create_picking_from_pos_order_lines`` crea los pickings sin
  ``_action_done()``, los encola con sus líneas y dispara el cron. Con la reserva diferida,
  ``_pos_queue_create_moves`` solo crea los moves en borrador (mismas agrupaciones que el core); la
  cola los completa en ``pos.inventory.queue._complete_deferred_picking``. Con la cola apagada o sin
  el contexto delega en el core.
- ``models/pos_config.py``: ``_create_sequences`` deja en ``standard`` la numeración de órdenes, líneas y
  referencia backend de cada POS nuevo (``_pos_queue_standard_sequences``); la usan también
  ``migrations/19.0.1.2.0/post-migrate.py`` y el ``post_init_hook`` para los POS existentes.
- ``models/pos_session.py``: la guarda de cierre en ``_validate_session``, que antes de dejar cerrar
  drena en línea los ítems de la sesión a través de ``_process_session_items``.
- ``models/stock_move.py``: ``_get_related_invoices`` (ver *Limitaciones conocidas*).
- ``data/``: secuencia ``PIQ/``, las dos acciones planificadas y el parámetro del interruptor, todo en
  ``noupdate="1"``.
- ``views/``: lista, formulario y búsqueda de la cola, y la ventana del interruptor con sus menús.
- ``migrations/17.0.2.1.0/pre-migrate.py``: columna ``next_retry_date`` (ver *Instalación*).
- ``migrations/19.0.1.2.0/post-migrate.py``: numeración de venta de los POS existentes a ``standard``.
- ``tests/test_queue_model.py``: 53 pruebas ``TransactionCase`` sobre secuencia, duplicados, reclamo,
  ``next_retry_date``, orden de proceso, reclamo de *Processing* vencido, cierre de sesión (items
  pendientes, fallidos, pickings validados a mano y la confirmación de foto previa a la lectura
  final), limpieza, botones, alerta de fallo permanente (creación, idempotencia y destinatarios) y
  recálculo del costo FIFO/AVCO tras validar el picking, conexión que no abre y liberación de
  los locks de stock de sesión (tras éxito, error de lógica y contención), y reserva diferida
  (venta sin reserva, la cola completa el picking, lote, interruptor apagado, devolución parcial
  con el picking en cola y devolución de una venta procesada) y numeración de venta ``standard``
  (POS nuevo y conversión idempotente sin saltos), y PDF de la factura después de confirmar
  (sin PDF dentro de la venta, generación aislada, interruptor apagado, ``generate_pdf=False``
  explícito y respaldo al cron), y el picking de la venta por el método del core (encolado normal,
  devolución de *Enviar más tarde* y backorders vinculados).
- ``tools/``: dos scripts de carga independientes, fuera de la suite de Odoo, que corren contra una
  base real. ``test_pos_inventory_concurrency.py`` encola ``--pickings`` ventas y las procesa con
  ``--drainers`` drenadores concurrentes (1 = cron normal; más = cron y cierres de caja
  simultáneos); verifica conexiones, stock y cola antes de empezar, valida pickings, stock físico,
  fechas y locks al terminar, y clasifica el resultado: ⛔ entorno (código 2), ❌ módulo (código 1),
  ⚠️ mejora u ✅ OK (código 0). ``--workers`` queda como alias de ``--drainers``.
  ``test_pos_sales_concurrency.py`` simula tiendas vendiendo a la vez: un proceso por cajero
  (``--cashiers`` por sesión abierta), ventas por ``pos.order.sync_from_ui`` con el reintento
  automático del servidor, reenvío de las que fallan como hace el POS, y la cola drenada por el cron
  real; valida ventas únicas, pickings, cola, stock físico y locks, con la misma clasificación.
  ``test_pos_invoice_concurrency.py`` es la versión anterior: pone todos los workers en una sesión,
  hace que cada venta drene la cola y da *PASS* aunque fallen órdenes, así que su veredicto no es
  confiable.

Notas para mantenimiento
------------------------

- **Transacciones.** El ítem se crea en la misma transacción que la orden y el picking; el cron solo
  lo ve después del commit, y ``ir.cron._trigger()`` queda escrito en esa misma transacción. La cola
  nunca confirma ni revierte la transacción de la venta.
- **Reclamo.** ``_claim_next_item`` usa ``SELECT ... FOR UPDATE SKIP LOCKED`` y marca *Processing* en el
  cursor del cron, que **confirma** antes de procesar para soltar el bloqueo de la fila. Por eso
  ``_process_queue`` solo debe llamarse sobre un cursor descartable (cron, tests o scripts), nunca
  desde una petición con trabajo propio sin confirmar.
- **Procesamiento.** Cada ítem se procesa en un cursor nuevo del registro, con ``SUPERUSER_ID`` y la
  compañía del picking, en un savepoint. Al empezar cada intento repite ``SET LOCAL lock_timeout``
  (5 s), porque un rollback lo borra, y toma un lock de sesión ``pg_advisory_lock`` por cada par
  (producto, compañía), en orden ascendente para evitar interbloqueos entre workers. Después de
  tomarlos confirma, para que la transacción de trabajo arranque con una foto posterior a la
  espera, y en el ``finally`` los suelta con ``pg_advisory_unlock_all()``: la conexión vuelve al pool
  sin limpiarse y, si no, el siguiente uso los heredaría.
- **Concurrencia.** Varios workers pueden drenar en paralelo; no hay bloqueo global. Dos ítems
  con productos distintos avanzan a la vez; dos con el mismo producto y compañía se esperan.
- **Idempotencia.** ``create`` devuelve el ítem existente si el picking ya está en cola, y la
  restricción ``UNIQUE(picking_id)`` junto con un savepoint cubre la carrera entre dos peticiones.
  Si el picking ya está hecho, el ítem se marca *Done* sin revalidar. *Retry* sobre un ítem que no
  está fallido no hace nada. El índice parcial ``pos_inventory_queue_claim_idx`` se crea con
  ``IF NOT EXISTS`` en cada instalación o actualización.
- **Dos políticas de reintento.** Contención: reintento inmediato, hasta 5 intentos, y vuelta a
  *Pending* sin consumir ciclos. Error de lógica: *Failed* con `next_retry_date = ahora + 2^n
  minutos` y *Failed Permanent* al quinto ciclo. Un error de conexión a mitad del trabajo deja el
  ítem en *Processing* para el reclamo por vencimiento; si no se puede abrir la conexión (pool de
  Odoo agotado o PostgreSQL sin cupo), el ítem vuelve a *Pending* y esa pasada termina.
- **El interruptor solo decide el encolado.** El procesador drena siempre, para que apagar la cola
  no deje pickings sin validar.

Changelog
=========

19.0.1.2.0 (2026-09-30)
-----------------------

- **Numeración de venta del POS como en Odoo 17**: Odoo 19 crea las secuencias de órdenes, líneas y
  referencia backend de cada POS ``no_gap`` (``pos_config._create_sequences``); la venta las bloquea
  (``FOR UPDATE NOWAIT``) hasta el commit, así que los cajeros de una tienda se esperaban entre sí y,
  con carga, el POS mostraba *could not obtain lock on row in relation "ir_sequence"*. En Odoo 17
  eran ``standard`` (verificado en staging: las 21 tiendas). Los POS nuevos nacen ``standard`` y el
  script ``migrations/19.0.1.2.0/post-migrate.py`` (idempotente) convierte los existentes; la
  numeración continúa sin saltos. No es numeración fiscal: la factura electrónica (Jorels 19) usa
  ``account_move.name`` y la resolución DIAN. Efecto esperado: un reintento de venta puede saltar un
  número interno de orden, igual que en 17.
- **PDF de la factura después de confirmar la venta**: el core publica la factura (toma el número
  del diario, sin huecos) y en la misma transacción genera y envía el PDF (``_generate_and_send``,
  2-3 s), con el número tomado: las ventas del mismo diario hacían fila (en producción ~20 POS
  comparten el diario ``FECO``). Ahora la venta factura sin PDF (``generate_pdf=False``, opción del
  core) y el PDF se genera en un post-commit, con el mismo llamado, usuario y contexto: después de
  confirmar la venta y antes de responder al POS, que recibe la factura con su PDF real. La
  validación DIAN de Jorels sigue en ``_post`` y su extensión del envío (ZIP firmado en el correo)
  corre igual. Si el PDF falla, la factura queda para el cron nativo *Send invoices
  automatically*. Interruptor ``pos_inventory_queue.invoice_pdf_after_commit``. Prueba a ritmo real
  (3 tiendas × 3 cajeros): p95 de la venta de 30 s a 6,5 s.
- **``_create_order_picking`` delega en Odoo 19** (PIQ-5): era una copia del método de Odoo 17 sin
  ``super()`` y le faltaban dos ramas de 19. Ahora llama al método del core con el contexto
  ``pos_inventory_queue=True``, que es lo que activa la cola. Recupera la devolución de una venta
  *Enviar más tarde* (cancela o reduce la entrega pendiente en vez de lanzar la regla de
  abastecimiento) y la cola vincula los backorders a la sesión y la orden al validar. Se pierde el
  respaldo de 17 para un tipo de operación sin ubicación destino, como en el core 19. En STG 17
  ningún POS usa *Enviar más tarde*: corrección preventiva.

53 pruebas automatizadas.

19.0.1.1.0 (2026-09-29)
-----------------------

Corrección de los cuatro hallazgos de la validación en Odoo 19 (PIQ-1 a PIQ-4). No cambia datos
ni esquema: no hace falta script de migración.

- **Costo FIFO/AVCO de la orden** (PIQ-1): el costo de las líneas FIFO/AVCO se recalcula recién
  cuando la cola valida el picking; antes salía en 0 porque el core lo calcula con movimientos sin
  validar, y el cierre de sesión nunca lo corregía. El margen de esas órdenes quedaba mal.
- **Alerta de fallo permanente** (PIQ-2): nunca se creaba: el dominio usaba ``groups_id`` (en 19 es
  ``group_ids``) y la actividad se anclaba a la cola, que no tiene ``mail.thread``. Ahora se ancla al
  picking y se crea una sola vez por picking y gestor de inventario.
- **Cierre de sesión en el primer intento** (PIQ-3): la lectura final de la guarda se hacía con la
  foto antigua de la transacción (los cursores de Odoo corren en REPEATABLE READ) y no veía que los
  cursores aislados habían marcado los ítems *Done*. Ahora confirma antes de leer.
- **Pickings validados a mano** (PIQ-4): la guarda del cierre saltaba esos ítems y quedaban
  bloqueando hasta pulsar *Retry*; ahora se reconcilian a *Done* (sin revalidar) y los ítems
  fallidos se reintentan en el cierre, de modo que si su causa ya se resolvió no bloquean.
- **Choques entre drenadores simultáneos**: el lock por producto se tomaba con
  ``pg_advisory_xact_lock``, pero PostgreSQL fija la foto de la transacción al empezar a esperar el
  lock, no al obtenerlo. El drenador que esperaba su turno trabajaba con datos viejos y chocaba
  igual en ``stock_quant``. Ahora el lock es de sesión (``pg_advisory_lock``), se confirma antes de
  trabajar y se suelta siempre. Con 30 drenadores sobre un mismo producto: de 368 choques y 84
  ventas devueltas a *Pending* a ninguno. Importa a la hora de cierre, cuando el cron y los cierres
  de caja de varias tiendas drenan a la vez.
- **Sin conexión para procesar**: si PostgreSQL no daba conexión (``too many clients``), el ítem
  quedaba en *Processing* hasta el reclamo de 5 minutos, sin fecha de fin. Ahora vuelve a *Pending*
  al instante y el cron lo toma en el siguiente ciclo.
- **La reserva de stock pasa de la venta a la cola**: la venta creaba el picking, lo confirmaba
  (con ``reservation_method = at_confirm`` eso reserva) y asignaba lotes con
  ``_add_mls_related_to_order``, todo dentro de su transacción y bloqueando ``stock_quant``: con varios
  cajeros vendiendo los mismos productos, chocaban. Ahora la venta deja el picking en borrador y el
  ítem guarda sus líneas (``pos_line_ids``, campo nuevo); la cola confirma, reserva, asigna lotes y
  valida con las mismas funciones del core. Interruptor ``pos_inventory_queue.defer_reservation``
  para volver al comportamiento anterior sin desinstalar. Los ítems que ya estaban en cola siguen
  el camino anterior: no hace falta script de migración.
- **Prueba de carga reescrita** (``tools/test_pos_inventory_concurrency.py``): separa ventas
  (``--pickings``) de drenadores (``--drainers``), verifica el entorno antes de empezar, valida el
  stock físico (no el disponible, que las reservas distorsionan) y clasifica el resultado en error
  del entorno, error del módulo u oportunidad de mejora.

Nueva prueba de ventas concurrentes ``tools/test_pos_sales_concurrency.py`` (tiendas, cajeros,
``sync_from_ui`` con el reintento del servidor, cron real).

19 → 43 pruebas automatizadas.

Credits
=======

Authors
-------

- Miguel Bolivar
- Libertario Coffee

Contributors
------------

- Miguel Bolivar
