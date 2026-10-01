## 19.0.1.2.0 (2026-09-30)

- **Numeración de venta del POS como en Odoo 17**: Odoo 19 crea las secuencias de órdenes, líneas y
  referencia backend de cada POS `no_gap` (`pos_config._create_sequences`); la venta las bloquea
  (`FOR UPDATE NOWAIT`) hasta el commit, así que los cajeros de una tienda se esperaban entre sí y,
  con carga, el POS mostraba *could not obtain lock on row in relation "ir_sequence"*. En Odoo 17
  eran `standard` (verificado en staging: las 21 tiendas). Los POS nuevos nacen `standard` y el
  script `migrations/19.0.1.2.0/post-migrate.py` (idempotente) convierte los existentes; la
  numeración continúa sin saltos. No es numeración fiscal: la factura electrónica (Jorels 19) usa
  `account_move.name` y la resolución DIAN. Efecto esperado: un reintento de venta puede saltar un
  número interno de orden, igual que en 17.
- **PDF de la factura después de confirmar la venta**: el core publica la factura (toma el número
  del diario, sin huecos) y en la misma transacción genera y envía el PDF (`_generate_and_send`,
  2-3 s), con el número tomado: las ventas del mismo diario hacían fila (en producción ~20 POS
  comparten el diario `FECO`). Ahora la venta factura sin PDF (`generate_pdf=False`, opción del
  core) y el PDF se genera en un post-commit, con el mismo llamado, usuario y contexto: después de
  confirmar la venta y antes de responder al POS, que recibe la factura con su PDF real. La
  validación DIAN de Jorels sigue en `_post` y su extensión del envío (ZIP firmado en el correo)
  corre igual. Si el PDF falla, la factura queda para el cron nativo *Send invoices
  automatically*. Interruptor `pos_inventory_queue.invoice_pdf_after_commit`. Prueba a ritmo real
  (3 tiendas × 3 cajeros): p95 de la venta de 30 s a 6,5 s.
- **`_create_order_picking` delega en Odoo 19** (PIQ-5): era una copia del método de Odoo 17 sin
  `super()` y le faltaban dos ramas de 19. Ahora llama al método del core con el contexto
  `pos_inventory_queue=True`, que es lo que activa la cola. Recupera la devolución de una venta
  *Enviar más tarde* (cancela o reduce la entrega pendiente en vez de lanzar la regla de
  abastecimiento) y la cola vincula los backorders a la sesión y la orden al validar. Se pierde el
  respaldo de 17 para un tipo de operación sin ubicación destino, como en el core 19. En STG 17
  ningún POS usa *Enviar más tarde*: corrección preventiva.

- **La cola usa su índice**: la búsqueda del siguiente ítem (`_claim_next_item`) no filtraba
  `active = True` y PostgreSQL no podía usar el índice parcial `pos_inventory_queue_claim_idx`
  (usaba el de `state`). Ahora lo usa y un ítem archivado no se procesa, como en el resto de Odoo.
  Se documenta que el orden de la cola es "mejor esfuerzo".

- **Vigía de la cola y las facturas** (acción planificada cada 5 minutos): avisa con una actividad
  a los gestores de inventario si la cola no avanza (antes nadie se enteraba hasta que una caja no
  podía cerrar) y a contabilidad si una factura del POS queda sin PDF. Intenta destrabar primero,
  no repite avisos y los cierra cuando el problema se resuelve. Resumen en vivo en la ventana
  *Inventario (Queue)*. Umbral `pos_inventory_queue.stall_alert_minutes` (15 min).
- Los mensajes de cierre de caja y de la alerta de fallo permanente apuntan al menú correcto
  (*Punto de Venta › Órdenes › Cola de Inventario*).

58 pruebas automatizadas.

## 19.0.1.1.0 (2026-09-29)

Corrección de los cuatro hallazgos de la validación en Odoo 19 (PIQ-1 a PIQ-4). No cambia datos
ni esquema: no hace falta script de migración.

- **Costo FIFO/AVCO de la orden** (PIQ-1): el costo de las líneas FIFO/AVCO se recalcula recién
  cuando la cola valida el picking; antes salía en 0 porque el core lo calcula con movimientos sin
  validar, y el cierre de sesión nunca lo corregía. El margen de esas órdenes quedaba mal.
- **Alerta de fallo permanente** (PIQ-2): nunca se creaba: el dominio usaba `groups_id` (en 19 es
  `group_ids`) y la actividad se anclaba a la cola, que no tiene `mail.thread`. Ahora se ancla al
  picking y se crea una sola vez por picking y gestor de inventario.
- **Cierre de sesión en el primer intento** (PIQ-3): la lectura final de la guarda se hacía con la
  foto antigua de la transacción (los cursores de Odoo corren en REPEATABLE READ) y no veía que los
  cursores aislados habían marcado los ítems *Done*. Ahora confirma antes de leer.
- **Pickings validados a mano** (PIQ-4): la guarda del cierre saltaba esos ítems y quedaban
  bloqueando hasta pulsar *Retry*; ahora se reconcilian a *Done* (sin revalidar) y los ítems
  fallidos se reintentan en el cierre, de modo que si su causa ya se resolvió no bloquean.
- **Choques entre drenadores simultáneos**: el lock por producto se tomaba con
  `pg_advisory_xact_lock`, pero PostgreSQL fija la foto de la transacción al empezar a esperar el
  lock, no al obtenerlo. El drenador que esperaba su turno trabajaba con datos viejos y chocaba
  igual en `stock_quant`. Ahora el lock es de sesión (`pg_advisory_lock`), se confirma antes de
  trabajar y se suelta siempre. Con 30 drenadores sobre un mismo producto: de 368 choques y 84
  ventas devueltas a *Pending* a ninguno. Importa a la hora de cierre, cuando el cron y los cierres
  de caja de varias tiendas drenan a la vez.
- **Sin conexión para procesar**: si PostgreSQL no daba conexión (`too many clients`), el ítem
  quedaba en *Processing* hasta el reclamo de 5 minutos, sin fecha de fin. Ahora vuelve a *Pending*
  al instante y el cron lo toma en el siguiente ciclo.
- **La reserva de stock pasa de la venta a la cola**: la venta creaba el picking, lo confirmaba
  (con `reservation_method = at_confirm` eso reserva) y asignaba lotes con
  `_add_mls_related_to_order`, todo dentro de su transacción y bloqueando `stock_quant`: con varios
  cajeros vendiendo los mismos productos, chocaban. Ahora la venta deja el picking en borrador y el
  ítem guarda sus líneas (`pos_line_ids`, campo nuevo); la cola confirma, reserva, asigna lotes y
  valida con las mismas funciones del core. Interruptor `pos_inventory_queue.defer_reservation`
  para volver al comportamiento anterior sin desinstalar. Los ítems que ya estaban en cola siguen
  el camino anterior: no hace falta script de migración.
- **Prueba de carga reescrita** (`tools/test_pos_inventory_concurrency.py`): separa ventas
  (`--pickings`) de drenadores (`--drainers`), verifica el entorno antes de empezar, valida el
  stock físico (no el disponible, que las reservas distorsionan) y clasifica el resultado en error
  del entorno, error del módulo u oportunidad de mejora.

Nueva prueba de ventas concurrentes `tools/test_pos_sales_concurrency.py` (tiendas, cajeros,
`sync_from_ui` con el reintento del servidor, cron real).

19 → 43 pruebas automatizadas.
