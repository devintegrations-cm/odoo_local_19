Limita qué **empleados** pueden **eliminar órdenes** en el Punto de Venta. Cada punto de venta tiene
una lista de empleados autorizados. Si el empleado que tiene la caja está en la lista, puede
eliminar órdenes como siempre. Si no está, el POS oculta el ícono de borrar en la pantalla de
*Órdenes* y rechaza la acción *Cancelar orden* con el aviso "No tiene permisos para eliminar una
orden, contacte al líder de tienda.".

Existe para que un cajero o mesero no pueda borrar una orden abierta (y con ella la venta) sin
pasar por el líder de tienda.

Con la lista vacía, todos los empleados pueden eliminar órdenes. Así se comportaba el POS antes de
instalar el módulo.
