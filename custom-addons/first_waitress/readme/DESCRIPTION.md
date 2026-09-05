Guarda al **primer** empleado que atendio el pedido del Punto de Venta. Agrega el campo *First
waitress* al pedido: se llena con el nombre del empleado la primera vez que se le asigna uno, y
**no se pisa** si despues el pedido se reasigna.

**No es lo mismo que el campo *Cashier* de Odoo**, que viene de `pos_hr`, y el campo del nucleo no
vuelve redundante a este modulo: *Cashier* refleja siempre al empleado **actual** y cae al usuario
si no hay empleado asignado, mientras que *First waitress* guarda al **primero**. Los dos coinciden
mientras nadie reasigne el pedido; en cuanto se reasigna, *Cashier* cambia y *First waitress*
conserva al original. Por eso el modulo sigue haciendo falta. No requiere configuracion: solo que
`pos_hr` este instalado, cosa que el modulo exige como dependencia.
