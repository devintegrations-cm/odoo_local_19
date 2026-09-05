Ir a *Punto de Venta > Configuración > Métodos de pago*, abrir el método con el
que se cobra con tarjeta y marcar **«Ask for approval number»**. La casilla está
debajo de «Identify Customer», en el formulario del método.

Odoo **no permite guardar** la configuración de un método de pago mientras haya
una sesión de POS abierta: para cambiar esta casilla hay que **cerrar la caja**
primero.

Después de guardar, recargar la pantalla del POS no alcanza: hay que volver a
entrar desde el backend (botón *Continue Selling* / *Open Register*) para que la
caja tome la nueva configuración.
