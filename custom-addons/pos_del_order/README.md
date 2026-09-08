# Delete Pos Order

Restringe quién puede **eliminar pedidos** desde el Punto de Venta.

En **Ajustes → Punto de Venta → Empleados (Advanced rights)** aparece *Allowed to
delete orders*. Con la lista vacía se permite a todos (comportamiento histórico);
con empleados listados, sólo ellos pueden eliminar.

## Cómo se aplica en Odoo 19

- `static/src/app/services/pos_store.js` parcha **`beforeDeleteOrder`**, el gancho
  del núcleo que *todas* las rutas de borrado atraviesan. En la versión de 17 el
  filtro estaba en `TicketScreen`, así que el botón de borrar de la pantalla de
  productos (`control_buttons.js` → `pos.onDeleteOrder`) lo saltaba: era un bypass
  del permiso, no un detalle de estilo.
- `static/src/app/screens/ticket_screen/ticket_screen.js` parcha
  `shouldHideDeleteButton`, que es lo que hace desaparecer el icono en lugar de
  mostrar un error al pulsarlo.
- La lista de empleados se lee de `config.raw` (ids crudos): el store sólo tiene
  cargados los empleados con sesión activa, y el getter relacional no resolvería
  los demás.

## Limitación conocida

La regla vive en el navegador: un usuario con acceso directo a RPC puede borrar un
pedido aunque no esté en la lista. Para un control real hace falta validar en
servidor sobre `pos.order` (o usar los permisos de `pos.role` de `pos_hr` 19, que
es el mecanismo nativo). En `doc/historial_16_17/` quedan las notas de la
migración 16→17.

## Pruebas

`tests/test_delete_order_access.py` (3): la lista llega al punto de venta desde
Ajustes, vacía por defecto, y el related es escribible.

## Licencia / Autor

OPL-1 — Osmar Toloza, Libertario Coffee
