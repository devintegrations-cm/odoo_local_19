## Limitaciones conocidas

- **La alerta de fallo permanente no se crea en Odoo 19.** `_notify_permanent_failure` busca los
  usuarios con `('groups_id', 'in', ...)`, pero en Odoo 19 el campo de `res.users` se llama
  `group_ids`. La búsqueda falla, el `except` lo captura y solo queda en el log la línea
  `POS Queue: PERMANENT no se pudo crear la alerta`. Además la actividad se crearía sobre
  `pos.inventory.queue`, que no hereda de `mail.activity.mixin`. Hoy la única señal de un fallo
  permanente es el log y la lista de la cola (QA_PREPRODUCCION_19, PIQ-2).
- **Costo de la línea en ventas encoladas.** El core calcula `total_cost` de las líneas justo
  después de `_create_order_picking()`, cuando la cola todavía no validó el picking. Con productos
  FIFO o AVCO, el costo sale de esos movimientos aún sin validar; QA lo reporta en 0 (PIQ-1). Si
  producción usa esos métodos, hay que verificarlo en staging.
- **El cierre de sesión puede fallar en el primer intento.** La guarda procesa los ítems en cursores
  aparte que confirman por su cuenta, pero la transacción del cierre vuelve a consultar la cola con
  su foto anterior de la base y todavía los ve sin *Done*. El segundo intento pasa (PIQ-3).
- **Picking validado a mano.** Si alguien valida el picking desde Inventario, el ítem no se marca
  *Done* y la guarda lo salta al drenar, así que bloquea el cierre hasta pulsar *Retry* (PIQ-4).
- **`_create_order_picking` reemplaza al del core sin llamar a `super()`.** Es copia del de Odoo
  17 y no incluye dos ramas que agregó Odoo 19: la devolución de una orden de envío posterior, que
  en el core usa el flujo de pickings, y la escritura de sesión, orden y origen en los
  `backorder_ids` (PIQ-5).
- **Presupuesto de tiempo del drenaje.** `_process_queue` corre hasta 240 segundos por pasada. Si
  el límite real de los cron del servidor (`limit_time_real_cron`) es menor, el worker puede morir
  antes y dejar un ítem en *Processing* hasta el reclamo de 5 minutos (PIQ-6, verificar en
  producción).
- **Rutas equivocadas en los mensajes.** El error de cierre de sesión y la nota de la alerta dicen
  *Punto de Venta › Configuración › Cola de Inventario*; el menú real es *Órdenes › Cola de
  Inventario*.
- **Código sin efecto visible.** `pos.session.queue_pending_count` y `action_view_queue_items` no
  aparecen en ninguna vista. El override de `stock.move._get_related_invoices` no tiene llamador en
  el fuente de Odoo 19 Community (solo lo extienden `sale_stock` y `purchase_stock`), y su
  comentario menciona `stock_valuation_layer`, que ya no existe en 19.
- **Limpieza por borrado.** La ayuda del campo `active` dice que los ítems se archivan, pero la
  limpieza semanal los borra (`unlink`). El filtro *Archived* de la búsqueda solo encuentra ítems
  archivados a mano.
- **Textos mezclados.** Las etiquetas de los campos, estados y filtros están en inglés sin
  traducción (*Pending*, *Retry*, *Done*); los mensajes al usuario y el menú, en español.
- Falta `static/description/icon.png`: en *Aplicaciones* se ve el ícono genérico de Odoo.

## Componentes

- `models/inventory_queue.py`: el modelo `pos.inventory.queue`. Reclamo de ítems, procesamiento
  en cursor aparte, bloqueos, reintentos, disparo del cron, alerta, botones y limpieza. Constantes:
  `MAX_RETRIES = 5`, `CLAIM_MAX_RETRIES = 10`, `STALE_PROCESSING_MINUTES = 5`,
  `LOCK_TIMEOUT_SECONDS = 5`.
- `models/inventory_queue_config.py`: la ventana del interruptor (`pos.inventory.queue.config`,
  transitorio), que lee y escribe `pos_inventory_queue.enabled`.
- `models/pos_order.py`: `_create_order_picking` con el contexto `pos_inventory_queue=True`, que
  es lo que activa la cola.
- `models/stock_picking.py`: `_create_picking_from_pos_order_lines` crea los pickings sin
  `_action_done()`, los encola y dispara el cron. Con la cola apagada o sin el contexto delega en el
  core.
- `models/pos_session.py`: la guarda de cierre en `_validate_session`.
- `models/stock_move.py`: `_get_related_invoices` (ver *Limitaciones conocidas*).
- `data/`: secuencia `PIQ/`, las dos acciones planificadas y el parámetro del interruptor, todo en
  `noupdate="1"`.
- `views/`: lista, formulario y búsqueda de la cola, y la ventana del interruptor con sus menús.
- `migrations/17.0.2.1.0/pre-migrate.py`: columna `next_retry_date` (ver *Instalación*).
- `tests/test_queue_model.py`: 19 pruebas `TransactionCase` sobre secuencia, duplicados, reclamo,
  `next_retry_date`, orden de proceso, reclamo de *Processing* vencido, cierre de sesión, limpieza
  y botones.
- `tools/`: dos scripts de carga independientes (`test_pos_inventory_concurrency.py` y
  `test_pos_invoice_concurrency.py`) que crean pickings u órdenes concurrentes contra una base real
  y verifican stock y estados. No forman parte de la suite de Odoo y tienen IDs por defecto de otro
  entorno: revisar sus parámetros con `--help` antes de usarlos.

## Notas para mantenimiento

- **Transacciones.** El ítem se crea en la misma transacción que la orden y el picking; el cron solo
  lo ve después del commit, y `ir.cron._trigger()` queda escrito en esa misma transacción. La cola
  nunca confirma ni revierte la transacción de la venta.
- **Reclamo.** `_claim_next_item` usa `SELECT ... FOR UPDATE SKIP LOCKED` y marca *Processing* en el
  cursor del cron, que **confirma** antes de procesar para soltar el bloqueo de la fila. Por eso
  `_process_queue` solo debe llamarse sobre un cursor descartable (cron, tests o scripts), nunca
  desde una petición con trabajo propio sin confirmar.
- **Procesamiento.** Cada ítem se procesa en un cursor nuevo del registro, con `SUPERUSER_ID` y la
  compañía del picking, en un savepoint. Al empezar cada intento repite `SET LOCAL lock_timeout`
  (5 s), porque un rollback lo borra, y toma `pg_advisory_xact_lock` por cada par (producto,
  compañía), en orden ascendente para evitar interbloqueos entre workers.
- **Concurrencia.** Varios workers pueden drenar en paralelo; no hay bloqueo global. Dos ítems
  con productos distintos avanzan a la vez; dos con el mismo producto y compañía se esperan.
- **Idempotencia.** `create` devuelve el ítem existente si el picking ya está en cola, y la
  restricción `UNIQUE(picking_id)` junto con un savepoint cubre la carrera entre dos peticiones.
  Si el picking ya está hecho, el ítem se marca *Done* sin revalidar. *Retry* sobre un ítem que no
  está fallido no hace nada. El índice parcial `pos_inventory_queue_claim_idx` se crea con
  `IF NOT EXISTS` en cada instalación o actualización.
- **Dos políticas de reintento.** Contención: reintento inmediato, hasta 5 intentos, y vuelta a
  *Pending* sin consumir ciclos. Error de lógica: *Failed* con `next_retry_date = ahora + 2^n
  minutos` y *Failed Permanent* al quinto ciclo. Un error de conexión deja el ítem en *Processing*
  para el reclamo por vencimiento; si el pool de conexiones está agotado, el ítem vuelve a *Pending*
  y esa pasada termina.
- **El interruptor solo decide el encolado.** El procesador drena siempre, para que apagar la cola
  no deje pickings sin validar.
