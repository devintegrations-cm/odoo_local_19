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
