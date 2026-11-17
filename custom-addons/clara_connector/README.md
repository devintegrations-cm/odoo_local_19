# Clara Connector (Libertario, solo lectura)

Fork de Libertario del conector oficial de Clara para Odoo, reducido desde la versión 2.0.0 a un **espejo de solo lectura** de las tarjetas corporativas y sus transacciones, con la trazabilidad contra las órdenes de compra de Odoo.

- **Solo lectura hacia Clara**: todas las llamadas a la API son `GET` (más el token OAuth). No se escriben comentarios, etiquetas, aprobaciones, rechazos ni bloqueos de tarjeta; el cliente (`services/clara_api_service.py`) rechaza cualquier otro método antes de enviar nada.
- **Solo lectura hacia Odoo**: ningún método del módulo crea, confirma ni modifica órdenes de compra. La orden ligada a una transacción se calcula a partir del código `P#####` que el bot de legalización escribe en la **primera línea del comentario de Clara**.
- **Ningún registro se crea, edita ni borra a mano**: transacciones, tarjetas y registros de sincronización son espejo de Clara; sus vistas no permiten crear, editar ni borrar.

Depende de `clara_purchase_bridge` (tabla de titulares y grupos de acceso).

## Sincronización semanal

Una única acción planificada, **Clara: sincronización semanal**, corre los **domingos a las 10:00 p. m. hora de Bogotá** (lunes 03:00 UTC; Colombia no tiene horario de verano), después de la pasada del bot de legalización. Pide a Clara lo mínimo:

1. **Transacciones**: solo las creadas o modificadas desde la sincronización anterior (`lastUpdateDateRangeStart` = última sincronización menos los *días que se releen*, 1 por defecto), en páginas de **100** (el máximo de la API). La primera corrida lee por fecha de operación desde *Primera sincronización desde* (o los últimos 90 días).
2. **Tarjetas**: todas, en páginas de 100 (una llamada para unas decenas de tarjetas).
3. **Enlaces**: la tarjeta de cada transacción, la regla de titular de tarjetas y transacciones sin regla, y la orden de las transacciones «Aprobadas sin orden» (una orden registrada después de la corrida anterior queda ligada en esta).

Solo se escriben los registros que cambiaron (el registro de sincronización lo muestra: creados, actualizados, sin cambios, llamadas a la API). La fecha de última sincronización avanza únicamente si todos los registros se guardaron. El día y la hora se cambian en Ajustes › Técnico › Acciones planificadas.

**«Sincronizar ahora»** (botón en las listas de transacciones y tarjetas, y en Ajustes › Clara) ejecuta la misma corrida a mano. Solo lo ve y lo puede ejecutar «Clara / Administrador».

## Modelos

### `clara.transaction`

Titular, fecha, comercio, monto, tipo (PURCHASE, PAYMENT, FEE...), estado de la operación, tarjeta (últimos 4 y enlace a `clara.card`), comentario de Clara, **estado en Clara** (`approval_status`: lo que decidió el revisor, `Approved`, `Needs Approval`, `Rejected`), comprobante, área y cuenta analítica (de la tabla de titulares), y:

- `purchase_order_id` (calculado, almacenado): la orden de compra cuyo nombre es el código `P#####` de la primera línea del comentario de Clara. Las órdenes canceladas no cuentan.
- `reconciliation_state` (calculado, almacenado), solo para compras con dinero cobrado:
  - **Conciliada**: aprobada en Clara y con orden existente.
  - **Aprobada sin orden**: aprobada en Clara y sin orden (o con la orden cancelada).
  - **Pendiente**: sin legalizar en Clara.
  - **Rechazada**: rechazada en Clara.
  Pagos, cuotas de manejo e intentos declinados quedan sin estado y fuera del filtro «Compras» (activo por defecto).
- `reconciled_ratio`: 100 si está conciliada, 0 si no; su promedio por mes es el **porcentaje conciliado** de la gráfica.

El payload de Clara se guarda **sin el número de la tarjeta ni documentos de identidad**.

### `clara.card`

Titular (nombre, uuid y correo de Clara), **últimos 4 dígitos**, tipo (física o virtual), estado (activa, bloqueada, inactiva o cancelada; `status_raw` conserva el estado y bloqueo tal como los envía Clara), límite mensual, periodicidad, área y cuenta analítica tomadas de `clara.analytic.rule` (por uuid, correo o nombre del titular). **Nunca se guarda el número completo de la tarjeta ni la cédula**: el payload de las tarjetas no se almacena.

Cuando la tabla de titulares cambia, tarjetas y transacciones vuelven a buscar su regla.

## Menú Clara › Dashboard

| Vista | Qué muestra |
|---|---|
| **Tarjetas** | Lista agrupada por área, bloqueadas en rojo; kanban por estado con el conteo de cada columna. |
| **Transacciones** | Titular, fecha, comercio, monto, estado en Clara, orden ligada y conciliación; filtros por mes, titular, área, estado de conciliación y estado en Clara. |
| **Trazabilidad** | Pivote titular × mes con el conteo y el monto de cada estado de conciliación; gráfica de línea del porcentaje conciliado por mes (con el filtro «Aprobadas en Clara» la gráfica muestra la proporción de aprobadas que ya tienen orden). |

Además: **Sincronizaciones** (registros de cada corrida) y, para administradores, **Configuración** (Ajustes y la tabla de titulares).

## Permisos

| Grupo | Puede |
|---|---|
| **Clara / Lectura** | Ver todo el menú Clara. No crea, edita ni borra ningún registro. Lo reciben los usuarios de Contabilidad y Finanzas (cualquier rol del módulo de Contabilidad). |
| **Clara / Administrador** | Configurar la API (Ajustes › Clara), ejecutar «Sincronizar ahora» y editar la tabla de titulares. Lo reciben los administradores del sistema. |

Los grupos se definen en `clara_purchase_bridge`. El Client ID, el Secret y los certificados mTLS de la compañía son campos del grupo «Clara / Administrador»: cualquier otro usuario recibe un error de acceso al leerlos; el servicio de la API los lee como superusuario, así que la corrida semanal funciona sin importar quién la dispare.

## Ajustes (Ajustes › Clara, solo administradores)

| Parámetro | Por defecto | Para qué |
|---|---|---|
| Credenciales y certificados mTLS | — | Conexión con la API de Clara; «Probar conexión» pide el token y lee una transacción. |
| `clara_connector.clara_request_timeout` | 30 | Segundos máximos por llamada. |
| `clara_connector.page_size` | 100 | Transacciones por página (máximo 100). |
| `clara_connector.sync_start_date` | últimos 90 días | Solo para la primera sincronización: fecha de operación inicial. |
| `clara_connector.sync_overlap_days` | 1 | Días que se releen antes de la última sincronización. |
| `clara_connector.monthly_call_limit` | 2500 | Tope mensual de llamadas (el plan incluye unas 3.000). |
| `clara_connector.last_sync_date` | — | Lo escribe la sincronización: fecha de la última corrida completa. |

## Migración a 2.0.0

- Se borran los crons anteriores (transacciones cada 6 h, tarjetas a diario, órdenes cada 30 min y la corrida semanal que registraba órdenes) y se crea la sincronización semanal.
- Se borran los parámetros de las funciones eliminadas (creación de órdenes, piloto, etiquetas, bloqueo de tarjetas, Anthropic, gastos y asientos, intervalos). La fecha de la última sincronización anterior pasa a `clara_connector.last_sync_date`.
- Los usuarios de los grupos antiguos «Clara User» y «Clara Manager» pasan a «Clara / Lectura» y «Clara / Administrador».
- Ninguna transacción ni tarjeta se borra: cada una se reescribe desde su propio payload, sin el número de la tarjeta, para llenar los campos nuevos (tipo, estado, límite, comentario, legalización, orden ligada, conciliación). No se toca ninguna orden de compra.
- Los modelos eliminados (facturas CFDI, campos contables, asistente de sincronización) dejan sus tablas en la base; Odoo no las borra en una actualización.

## 2.0.2

- El menú Clara usa el icono oficial de Clara (la marca de la app). El icono anterior era un píxel verde que Odoo
  estiraba como un cuadro. Sin cambios de datos ni de comportamiento.

## Migración a 2.0.1

- Se eliminan de la base las columnas de cédula de versiones anteriores (`clara_transaction.cardholder_vat` y `clara_transaction.receipt_issuer_vat`), solo si existen. No se toca ninguna otra columna ni tabla.
- Las credenciales de la API (Client ID, Secret y certificados) quedan restringidas al grupo «Clara / Administrador».
- La paginación lee `last` y `totalPages` solo cuando Clara responde un objeto de página; una lista plana se sigue pidiendo hasta la página vacía.
- Al final de cada corrida se recalcula también la orden ligada de las transacciones pendientes con código P##### en el comentario y de las que tenían ligada una orden ya cancelada.

## Pruebas

```bash
odoo -d <base> -i clara_purchase_bridge,clara_connector --test-enable --test-tags /clara_purchase_bridge,/clara_connector --stop-after-init
```

Las pruebas comprueban, entre otras cosas, que ningún método de los módulos crea ni escribe `purchase.order`, que ninguna llamada a Clara usa un método distinto de `GET` y que `reconciliation_state` se calcula bien en sus cuatro casos.
