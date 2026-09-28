## Limitaciones conocidas

- **El checklist solo se carga desde el formulario.** Lo trae el cambio de equipo en la pantalla;
  las solicitudes creadas por importación, por código o como repetición de un preventivo
  recurrente quedan sin checklist y, por lo tanto, sin bloqueo al cerrar.
- **El bloqueo solo revisa el cambio de etapa.** Una solicitud creada directamente en una etapa de
  cierre no se valida.
- **Traer costos de OC no evita duplicados.** Cada pulsación copia de nuevo todas las líneas de la
  orden, aunque ya se hayan traído.
- **Regla del número de serie sin confirmar.** El código la marca como pendiente de validar con el
  negocio (longitud de las abreviaturas, separadores, fecha de creación o de puesta en marcha). El
  parámetro `maintenance_management.serial_pattern` que menciona el código **no existe** en la base
  ni cambia nada: la regla está fija en `_compute_or_default_serial()`. La serie tampoco es única.
- **La hoja de vida es pública para quien tenga el QR.** Muestra la ficha completa, incluidos el
  cliente, el proveedor y el técnico responsable. El módulo no ofrece una forma de renovar el token
  desde la interfaz si una etiqueta se pierde.
- **Permisos amplios.** Cualquier usuario interno puede crear, modificar y borrar plantillas de
  checklist y líneas de costo; el menú de plantillas es lo único restringido a *Responsable de los
  equipos*.
- **Una plantilla por categoría.** Si hay varias, se usa la primera que encuentra Odoo.
- **Columna *Moneda* vacía en las líneas de costo.** El campo está marcado `invisible="1"` dentro de
  la lista; en Odoo 19 eso oculta el valor pero deja la columna. Es solo estético.
- **Textos fijos en español.** Las vistas, los reportes y los mensajes están escritos en español en
  el código y el módulo no trae carpeta `i18n/`: un usuario con Odoo en otro idioma los ve igual.
- Falta `static/description/icon.png`: en *Aplicaciones* se ve el ícono genérico de Odoo.

## Componentes

- `models/maintenance_equipment.py`: número de activo, tienda, cliente, QR (`portal.mixin`), costo
  acumulado, serie por defecto y las acciones de los botones y de *Asignar Nº de activo, QR y
  serial*. El código de tienda del serial sale de `_get_store_code()`, aislado para poder cambiar
  su origen sin tocar lo demás.
- `models/maintenance_request.py`: referencia, condición, ubicación, checklist, costos, carga de la
  plantilla (`_onchange_equipment_id`), bloqueo de cierre (`write`) y `action_bring_costs_from_po`.
- `models/maintenance_checklist.py`: plantillas, ítems de plantilla e ítems de la solicitud.
- `models/maintenance_request_cost_line.py`: líneas de costo, con enlace a la línea de compra de
  origen.
- `controllers/portal.py` y `views/maintenance_portal_templates.xml`: la ruta `/my/equipment/<id>`
  y la hoja de vida. Valida el acceso con `_document_check_access` (token o permisos del usuario).
- `report/qr_label_report.xml` y `report/maintenance_report.xml`: etiqueta QR y orden de
  mantenimiento. El QR va embebido como imagen, sin servicio externo.
- `data/`: secuencias `ACT` e `INC`, el parámetro `enforce_checklist` y la acción de servidor.
- `demo/demo_data.xml`: categorías y plantillas de ejemplo, solo en bases con demostración.

## Notas para mantenimiento

- **Sin tests automáticos.** El módulo no tiene carpeta `tests/`; todo se valida a mano.
- **El QR depende de `web.base.url`.** Se calcula al vuelo (no se guarda) con la URL base y el token
  del equipo. Si cambia la dirección del servidor, las etiquetas ya impresas apuntan a la
  dirección vieja.
- **Traer costos automáticamente.** `action_bring_costs_from_po()` está aislado para poder llamarlo
  más adelante al confirmar la compra o desde un cron; hoy es solo manual.
- **Migración 17 → 19.** El campo `location` de `maintenance.equipment` desapareció del core en 19;
  si se vuelve a usar en la plantilla del portal, la hoja de vida falla con `AttributeError`. En
  Odoo 19 el campo *Usado en la ubicación* del equipo lo agrega `stock_maintenance` y no lo usa este
  módulo.
- **Moneda de los costos.** La solicitud toma por defecto la moneda de la compañía activa al
  crearla, en lugar de un campo relacionado con su compañía, para no fallar si la solicitud no
  tiene compañía resuelta. Las líneas de costo usan la moneda de su solicitud.
