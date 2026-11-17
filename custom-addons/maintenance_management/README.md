# Gestión Integral de Mantenimiento (`maintenance_management`) — Odoo 19

Extiende el módulo base `maintenance` de Odoo 19 CE con:

- Ficha técnica y trazabilidad de activos (número de activo, tienda/almacén,
  cliente, código QR con hoja de vida pública en el portal).
- Solicitudes de mantenimiento enriquecidas: referencia interna, condición
  del equipo, checklist configurable por categoría, líneas de costo (con
  posibilidad de traerlas desde una orden de compra) y reporte imprimible.

Este README documenta la capa de datos/vista entregada; los modelos Python
se implementan en `models/` (ver contrato técnico del proyecto).

## Dependencias

`maintenance`, `portal`, `purchase`, `stock`.

## Campos nuevos

### `maintenance.equipment`

| Campo | Tipo | Descripción |
|---|---|---|
| `asset_number` | Char, único, readonly | Número de activo asignado automáticamente por secuencia al crear el equipo. |
| `warehouse_id` | Many2one `stock.warehouse` | Tienda/almacén donde está ubicado el equipo. |
| `customer_id` | Many2one `res.partner` | Cliente asociado al equipo (útil para equipos en comodato). |
| `qr_image` | Binary (computado, no almacenado) | Código QR que enlaza a la hoja de vida en el portal (`/my/equipment/<id>`). |
| `maintenance_total_cost` | Monetary (computado) | Suma de `total_cost` de todas las solicitudes de mantenimiento del equipo. |

Hereda también `portal.mixin` (campos `access_url` / `access_token`).

### `maintenance.request`

| Campo | Tipo | Descripción |
|---|---|---|
| `reference` | Char, readonly | Número de incidencia asignado automáticamente por secuencia. |
| `equipment_condition` | Selection (Bueno/Regular/Malo) | Condición del equipo reportada por el técnico. |
| `action_taken` | Text | Observaciones / acciones realizadas durante el mantenimiento. |
| `maintenance_location_id` | Many2one `stock.warehouse` | Ubicación donde se ejecuta el mantenimiento (por defecto, la tienda del equipo). |
| `checklist_line_ids` | One2many `maintenance.checklist.line` | Checklist de la solicitud, autocompletado desde la plantilla de la categoría del equipo. |
| `cost_line_ids` | One2many `maintenance.request.cost.line` | Líneas de costo del mantenimiento. |
| `total_cost` | Monetary (computado, almacenado) | Suma de `cost_line_ids.amount`. |
| `purchase_order_id` | Many2one `purchase.order` | Orden de compra de referencia para traer costos. |

### Modelos nuevos

- `maintenance.request.cost.line`: línea de costo de una solicitud (detalle,
  producto, cantidad, valor, línea de OC de origen).
- `maintenance.checklist.template` / `maintenance.checklist.template.line`:
  plantilla de checklist por categoría de equipo (Configuración > Plantillas
  de Checklist).
- `maintenance.checklist.line`: línea de checklist de una solicitud concreta
  (ítem, realizado, nota).

## Secuencias

| Código | Prefijo | Padding | Uso |
|---|---|---|---|
| `maintenance.management.asset` | `ACT` | 5 | `asset_number` de `maintenance.equipment`. |
| `maintenance.management.incident` | `INC` | 5 | `reference` de `maintenance.request`. |

## Parámetros de sistema (`ir.config_parameter`)

- **`maintenance_management.serial_pattern`**: informativo/documental. La
  regla de generación automática del `serial_no` (cuando el usuario lo deja
  vacío) está implementada en código en
  `maintenance.equipment._compute_or_default_serial()`. Regla por defecto:
  3 primeras letras de las 2 primeras palabras del nombre del equipo (en
  mayúsculas, sin tildes) + código de tienda (`warehouse_id.code`, ver
  `_get_store_code()`) + fecha de registro `AAAAMMDD`.
  Ejemplo: equipo "Nevera de cocina", tienda `ZNG2`, registrado el
  2025-05-08 → `NEVCOCZNG220250508`.
  **TODO / pendiente de confirmar con el negocio:** la regla exacta de
  composición del serial (longitud de las abreviaturas, separadores, si se
  debe usar la fecha de creación o la fecha de puesta en marcha). Está
  centralizada en un único método para poder ajustarla sin tocar el resto
  del módulo.
- **`maintenance_management.enforce_checklist`** (`True` por defecto): si
  está activo, no se puede llevar una solicitud a una etapa marcada como
  "Realizado" (`stage_id.done = True`) mientras existan ítems de checklist
  sin marcar (`is_done = False`). Se puede desactivar por parámetro de
  sistema para clientes que no requieran ese control.

## Decisiones de diseño / TODOs

- El código de tienda usado en el serial se obtiene mediante
  `maintenance.equipment._get_store_code()`, aislado a propósito: hoy
  devuelve `warehouse_id.code`, pero si el negocio define otro origen del
  código de tienda basta con cambiar ese método.
- `action_bring_costs_from_po()` es una acción manual (botón "Traer costos
  de OC"), no automática, para que el técnico decida el momento de traer
  las líneas de la orden de compra. Queda como TODO evaluar si conviene
  automatizarlo (p. ej. al confirmar la OC).
- El QR se genera con `ir.actions.report.barcode()` (ya incluido en Odoo),
  evitando dependencias externas (`qrcode`/`PIL`). El PDF de la etiqueta y
  la página del portal embeben el QR como `data:image/png;base64,...`
  (no se expone una URL externa de generación de barcodes).
- El acceso a la hoja de vida (`/my/equipment/<id>`) usa
  `portal.mixin` + `_document_check_access`, igual que cualquier documento
  del portal: funciona tanto para un usuario público que escanea el QR
  (validado por `access_token`) como para un usuario logueado con permisos
  sobre el registro.
- `currency_id` en `maintenance.request` y en
  `maintenance.request.cost.line` no usa `related` sobre `company_id` para
  evitar romper si la solicitud no tiene compañía resuelta: en la solicitud
  se define con un `default` a la moneda de la compañía activa, y en la
  línea de costo es `related='request_id.currency_id', store=True`.

## Prueba manual

1. **Instalar el módulo** `maintenance_management` (depende de
   `maintenance`, `portal`, `purchase`, `stock`).
2. **Crear una categoría de equipo** (Mantenimiento > Configuración >
   Categorías de Equipo), por ejemplo "Neveras".
3. **Crear una plantilla de checklist** para esa categoría (Mantenimiento >
   Configuración > Plantillas de Checklist), con un par de ítems (p. ej.
   "Revisar empaques", "Medir temperatura").
4. **Crear un equipo** (Mantenimiento > Equipos) de esa categoría, sin
   indicar número de serie ni número de activo, y guardar:
   - Verificar que `asset_number` se asignó automáticamente (`ACT00001`,
     ...).
   - Verificar que `serial_no` se autocompletó siguiendo el patrón
     documentado arriba.
   - En la pestaña "Ficha técnica", asignar `warehouse_id` (tienda) y
     `customer_id` (cliente).
   - Verificar que se ve el campo `qr_image` en la ficha del equipo.
5. **Smart buttons del equipo**:
   - Pulsar "Hoja de Vida": debe abrir `/my/equipment/<id>` con la
     información del equipo, indicadores (MTBF/MTTR/Nº mantenimientos/costo
     acumulado) y el historial de solicitudes.
   - Pulsar "Imprimir QR": debe generar un PDF con el nombre del equipo, el
     número de serie en texto legible y el código QR.
   - Verificar que el botón de "Costo total" muestra 0 (aún sin
     solicitudes).
6. **Crear una solicitud de mantenimiento** para el equipo:
   - Verificar que se asigna automáticamente `reference` (`INC00001`, ...).
   - Verificar que `maintenance_location_id` se autocompleta con la tienda
     del equipo y que la pestaña "Checklist" trae los ítems de la plantilla
     de la categoría.
   - Completar `equipment_condition` y la pestaña "Diagnóstico" (acciones
     realizadas).
   - En la pestaña "Costos", agregar una línea manual de costo, o asociar
     una `purchase_order_id` y pulsar "Traer costos de OC" para copiar las
     líneas de la orden.
   - Verificar que `total_cost` se recalcula con la suma de las líneas.
7. **Checklist obligatorio**: con
   `maintenance_management.enforce_checklist` en `True` (valor por
   defecto), dejar al menos un ítem del checklist sin marcar y tratar de
   mover la solicitud a una etapa marcada como "Realizado": debe bloquear
   la operación con un mensaje de error. Marcar todos los ítems como
   realizados y repetir: debe permitir el cambio de etapa.
8. **Imprimir la orden de mantenimiento** (botón/acción de impresión de la
   solicitud): el PDF debe mostrar encabezado, equipo, condición,
   checklist con las marcas de "Realizado", líneas de costo con el total,
   observaciones, técnico y fechas.
9. **Portal**: volver a la hoja de vida del equipo y verificar que el
   historial de solicitudes ahora muestra la nueva solicitud con su
   ubicación, condición, costo y estado.

## Cambios vs Odoo 17 (Migración)

### Archivos modificados

- **`views/maintenance_portal_templates.xml`**: eliminada referencia a
  `equipment.location` (línea `<tr t-if="equipment.location">`). El campo
  `location` no existe en `maintenance.equipment` de Odoo 19 (fue eliminado
  del módulo base). La información de ubicación ya se muestra correctamente
  vía `equipment.warehouse_id` como "Tienda / Almacén" en el mismo template.
  Este cambio corrige el error `AttributeError: 'maintenance.equipment'
  object has no attribute 'location'` que ocurría al abrir la hoja de vida
  en el portal.

### Archivos sin cambios

Todos los demás archivos del módulo son compatibles con Odoo 19 sin
modificaciones:

- **Python**: modelos (`maintenance_equipment.py`, `maintenance_request.py`,
  `maintenance_request_cost_line.py`, `maintenance_checklist.py`) no
  dependen de APIs eliminadas o renombradas en v19.
- **Vistas XML**: usan sintaxis de dominio v19 (`invisible="..."` sin
  `attrs`), hereda de vistas base que siguen existiendo.
- **Datos**: secuencias, parámetros de sistema, acciones de servidor — sin
  cambios.
- **Reportes**: reportes QWeb compatibles con v19.
- **Seguridad**: CSV de permisos compatible.
- **Controladores**: portal routes compatibles.

### Campos eliminados de Odoo 19

| Campo | Ubicación original | Estado en v19 |
|---|---|---|
| `maintenance.equipment.location` | Campo Many2one del módulo base | Eliminado en Odoo 19. Reemplazado funcionalmente por `warehouse_id` en este módulo. |
