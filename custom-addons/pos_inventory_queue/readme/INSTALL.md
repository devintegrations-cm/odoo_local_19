## Dependencias

- `point_of_sale` (Odoo 19 Community). No hay dependencias externas ni librerías de Python
  adicionales.

## Pasos de instalación

Instalar el módulo desde *Aplicaciones*. Crea el modelo de la cola, su secuencia (`PIQ/000001`),
dos acciones planificadas, el parámetro del sistema `pos_inventory_queue.enabled` con valor `True`
y los menús *Órdenes › Cola de Inventario* y *Configuración › Inventario (Queue)*. Desde ese momento
la cola queda activa: no hace falta configurar nada más para que funcione.

El procesamiento depende de las acciones planificadas, así que el servidor tiene que correr con el
planificador de tareas habilitado (workers de cron).

## Migración desde Odoo 17

El módulo conserva el mismo nombre técnico y los mismos campos que en 17. Al actualizar desde la
versión `17.0.1.2.1` se ejecuta `migrations/17.0.2.1.0/pre-migrate.py`, que agrega la columna
`next_retry_date` a `pos_inventory_queue` solo si no existe; se puede ejecutar más de una vez sin
efecto. Los datos de acciones planificadas, secuencia y parámetro están en `noupdate="1"`: una
actualización no pisa el valor del interruptor ni los cambios hechos a los cron.

Respecto de 17 se retiraron tres piezas: el bloqueo de numeración de facturas
(`account_move._set_next_sequence`, que en Odoo 19 ya resuelve el core), el pool de conexiones
propio (ahora el drenaje corre en el worker de cron) y la vista en *Ajustes*, que en 17 no estaba
cargada en el manifiesto. Se agregaron la guarda de cierre de sesión, el reintento diferido
(`next_retry_date`) y la alerta de fallo permanente.
