Puente entre `pos_partner_performance` y `pos_settle_due` (Enterprise, *Liquidar deudas* en el POS).
Deja de calcular la **deuda de cada cliente** en el POS.

`pos_settle_due` calcula la deuda (órdenes y facturas pendientes) de cada cliente que carga el POS:

- al cargar los clientes del POS: ~60 s por página de 100 clientes (medido en staging);
- al abrir la caja, otra vez para todos los clientes cargados;
- después de cada búsqueda de clientes: hasta 27 s por búsqueda;
- después de cada venta pagada con *cuenta de cliente* (convenios): 20–46 s por venta.

El costo crece con la historia del cliente, no con lo que debe. El peor caso son los **clientes
por defecto** de cada tienda (*VENTA MOSTRADOR …*), que se cargan siempre: el de Zona G tiene
145.387 órdenes y 138.984 facturas, y solo su `total_due` tardó **37,7 s**, dos veces en cada
apertura de la caja.

En las cajas con **No calcular la deuda de los clientes** activado (por defecto):

- los clientes llegan al POS sin la deuda, y no se vuelve a pedir al abrir la caja ni al buscar;
- después de una venta con cuenta de cliente tampoco se recalcula (`pos_settle_due` solo lo hace si
  el cliente trae la deuda cargada).

Las deudas las gestiona Contabilidad en el backend; en el POS no se liquidan.
