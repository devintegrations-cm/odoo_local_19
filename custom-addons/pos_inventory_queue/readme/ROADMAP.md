## Limitaciones conocidas

- **Cliente repetido en las facturas.** Con `auth_signup.invitation_scope = b2c` (así está
  producción), publicar cada factura escribe en la ficha del cliente (`auth_signup` ›
  `signup_prepare`) si no tiene usuario y recibe la notificación. Si todas las tiendas le facturan
  al mismo cliente ("Consumidor final"), esas ventas chocan en esa fila. Es configuración, no del
  módulo; verificar en producción qué clientes concentran la facturación.
- **Devolución parcial de un producto con lote mientras su picking sigue en cola.** Se reduce la
  demanda del move, pero la cola asigna el lote según la cantidad de la línea original. Es una
  ventana de segundos; mismo comportamiento que tenía la reserva en la venta.

- **La cola solo actúa con stock "En tiempo real".** Si la compañía tiene *Actualizar cantidades
  en stock* = *Al cierre de la sesión*, las ventas del POS no crean picking (Odoo arma uno solo al
  cerrar) y la cola no interviene, salvo en ventas facturadas con contabilidad anglosajona
  (`pos.order._force_create_picking_real_time`). La base local está así; hay que confirmar la
  configuración de producción. La opción se copia a cada sesión al abrirla
  (`pos.session.update_stock_at_closing`), así que un cambio solo aplica a sesiones nuevas.
- **Presupuesto de tiempo del drenaje.** `_process_queue` corre hasta 240 segundos por pasada. Si
  el límite real de los cron del servidor (`limit_time_real_cron`) es menor, el worker puede morir
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
  comentario del código lo justifica con `stock_valuation_layer`, tabla que ya no existe en Odoo 19;
  falta verificar qué comparten de verdad las tiendas en la valoración de 19 antes de cambiarlo.
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
  en cursor aparte, bloqueos, reintentos, disparo del cron, alerta, recálculo del costo de la
  orden al validar el picking, botones y limpieza. Constantes: `MAX_RETRIES = 5`,
  `CLAIM_MAX_RETRIES = 10`, `STALE_PROCESSING_MINUTES = 5`, `LOCK_TIMEOUT_SECONDS = 5`.
- `models/inventory_queue_config.py`: la ventana del interruptor (`pos.inventory.queue.config`,
  transitorio), que lee y escribe `pos_inventory_queue.enabled`.
- `models/pos_order.py`: `_create_order_picking` llama al método del core con el contexto
  `pos_inventory_queue=True`, que es lo que activa la cola; y `_recompute_cost_after_queue`, que recalcula el costo FIFO/AVCO de
  la orden cuando la cola valida el picking (ver *Casos especiales* en *Uso*).
- `models/pos_order.py` (factura): `_generate_pos_order_invoice` factura sin PDF y lo agenda en un
  post-commit (`_pos_queue_schedule_invoice_pdf`); `_pos_queue_generate_invoice_pdf_isolated` lo
  genera en su propia transacción y, si falla, `_pos_queue_invoice_pdf_fallback` deja la factura al
  cron nativo de envío.
- `models/stock_picking.py`: `_create_picking_from_pos_order_lines` crea los pickings sin
  `_action_done()`, los encola con sus líneas y dispara el cron. Con la reserva diferida,
  `_pos_queue_create_moves` solo crea los moves en borrador (mismas agrupaciones que el core); la
  cola los completa en `pos.inventory.queue._complete_deferred_picking`. Con la cola apagada o sin
  el contexto delega en el core.
- `models/pos_config.py`: `_create_sequences` deja en `standard` la numeración de órdenes, líneas y
  referencia backend de cada POS nuevo (`_pos_queue_standard_sequences`); la usan también
  `migrations/19.0.1.2.0/post-migrate.py` y el `post_init_hook` para los POS existentes.
- `models/pos_session.py`: la guarda de cierre en `_validate_session`, que antes de dejar cerrar
  drena en línea los ítems de la sesión a través de `_process_session_items`.
- `models/stock_move.py`: `_get_related_invoices` (ver *Limitaciones conocidas*).
- `data/`: secuencia `PIQ/`, las dos acciones planificadas y el parámetro del interruptor, todo en
  `noupdate="1"`.
- `views/`: lista, formulario y búsqueda de la cola, y la ventana del interruptor con sus menús.
- `migrations/17.0.2.1.0/pre-migrate.py`: columna `next_retry_date` (ver *Instalación*).
- `migrations/19.0.1.2.0/post-migrate.py`: numeración de venta de los POS existentes a `standard`.
- `tests/test_queue_model.py`: 53 pruebas `TransactionCase` sobre secuencia, duplicados, reclamo,
  `next_retry_date`, orden de proceso, reclamo de *Processing* vencido, cierre de sesión (items
  pendientes, fallidos, pickings validados a mano y la confirmación de foto previa a la lectura
  final), limpieza, botones, alerta de fallo permanente (creación, idempotencia y destinatarios) y
  recálculo del costo FIFO/AVCO tras validar el picking, conexión que no abre y liberación de
  los locks de stock de sesión (tras éxito, error de lógica y contención), y reserva diferida
  (venta sin reserva, la cola completa el picking, lote, interruptor apagado, devolución parcial
  con el picking en cola y devolución de una venta procesada) y numeración de venta `standard`
  (POS nuevo y conversión idempotente sin saltos), y PDF de la factura después de confirmar
  (sin PDF dentro de la venta, generación aislada, interruptor apagado, `generate_pdf=False`
  explícito y respaldo al cron), y el picking de la venta por el método del core (encolado normal,
  devolución de *Enviar más tarde* y backorders vinculados).
- `tools/`: dos scripts de carga independientes, fuera de la suite de Odoo, que corren contra una
  base real. `test_pos_inventory_concurrency.py` encola `--pickings` ventas y las procesa con
  `--drainers` drenadores concurrentes (1 = cron normal; más = cron y cierres de caja
  simultáneos); verifica conexiones, stock y cola antes de empezar, valida pickings, stock físico,
  fechas y locks al terminar, y clasifica el resultado: ⛔ entorno (código 2), ❌ módulo (código 1),
  ⚠️ mejora u ✅ OK (código 0). `--workers` queda como alias de `--drainers`.
  `test_pos_sales_concurrency.py` simula tiendas vendiendo a la vez: un proceso por cajero
  (`--cashiers` por sesión abierta), ventas por `pos.order.sync_from_ui` con el reintento
  automático del servidor, reenvío de las que fallan como hace el POS, y la cola drenada por el cron
  real; valida ventas únicas, pickings, cola, stock físico y locks, con la misma clasificación.
  `test_pos_invoice_concurrency.py` es la versión anterior: pone todos los workers en una sesión,
  hace que cada venta drene la cola y da *PASS* aunque fallen órdenes, así que su veredicto no es
  confiable.

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
  (5 s), porque un rollback lo borra, y toma un lock de sesión `pg_advisory_lock` por cada par
  (producto, compañía), en orden ascendente para evitar interbloqueos entre workers. Después de
  tomarlos confirma, para que la transacción de trabajo arranque con una foto posterior a la
  espera, y en el `finally` los suelta con `pg_advisory_unlock_all()`: la conexión vuelve al pool
  sin limpiarse y, si no, el siguiente uso los heredaría.
- **Concurrencia.** Varios workers pueden drenar en paralelo; no hay bloqueo global. Dos ítems
  con productos distintos avanzan a la vez; dos con el mismo producto y compañía se esperan.
- **Idempotencia.** `create` devuelve el ítem existente si el picking ya está en cola, y la
  restricción `UNIQUE(picking_id)` junto con un savepoint cubre la carrera entre dos peticiones.
  Si el picking ya está hecho, el ítem se marca *Done* sin revalidar. *Retry* sobre un ítem que no
  está fallido no hace nada. El índice parcial `pos_inventory_queue_claim_idx` se crea con
  `IF NOT EXISTS` en cada instalación o actualización.
- **Dos políticas de reintento.** Contención: reintento inmediato, hasta 5 intentos, y vuelta a
  *Pending* sin consumir ciclos. Error de lógica: *Failed* con `next_retry_date = ahora + 2^n
  minutos` y *Failed Permanent* al quinto ciclo. Un error de conexión a mitad del trabajo deja el
  ítem en *Processing* para el reclamo por vencimiento; si no se puede abrir la conexión (pool de
  Odoo agotado o PostgreSQL sin cupo), el ítem vuelve a *Pending* y esa pasada termina.
- **El interruptor solo decide el encolado.** El procesador drena siempre, para que apagar la cola
  no deje pickings sin validar.
