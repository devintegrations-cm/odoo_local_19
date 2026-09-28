Permite reservar métodos de pago del Punto de Venta para **clientes autorizados**. En cada punto de
venta se define una lista de restricciones: cada una asocia un método de pago con los clientes que
pueden usarlo. En la pantalla de pago:

- un cliente con restricción ve **solo** los métodos que tiene autorizados;
- cualquier otro cliente, o una orden sin cliente, ve solo los métodos que no están restringidos.

Cada restricción puede además:

- pedir **datos adicionales** en un popup al elegir el método (por ejemplo huésped y habitación) y
  avisar si hoy ya se registró una orden con los mismos datos;
- decidir si la orden **se factura en el POS o no**, por encima de la facturación obligatoria;
- forzar la **entrega de inventario** en el momento de la venta.

Las órdenes que quedan sin factura se facturan después en una sola **factura agrupada** por cliente,
desde la lista de órdenes. El menú *Reportes › Convenios y restricciones* muestra las órdenes con
los datos capturados.

El caso que lo originó es el convenio de desayunos con un hotel: el huésped no paga, la orden queda
a nombre del hotel con los datos del huésped y se factura al hotel al cierre del mes.
