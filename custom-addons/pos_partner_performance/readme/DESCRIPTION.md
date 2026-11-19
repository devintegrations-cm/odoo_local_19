Hace más rápida la carga de clientes al abrir el Punto de Venta de Odoo 19. Es **opcional**: no se
instala solo, se activa **por caja** y desinstalarlo deja todo como en el estándar.

Al abrir la caja, el POS carga una lista de «clientes frecuentes» (100 por defecto). El estándar
de Odoo los ordena contando **todas las órdenes de POS de la base** en cada apertura y cada vez que
se pide otra página de clientes: con 853.810 órdenes (staging) son 6,6 s por llamada, y el
resultado mezcla todas las tiendas.

Con este módulo, en cada caja que lo tenga activado, el ranking cuenta solo las órdenes **de esa
caja** en los últimos **90 días** (configurable). Es más rápido y cada tienda carga primero a sus
propios clientes. El cliente por defecto de la caja (`pw_pos_default_customer`) se carga siempre.

Junto con `pos_settle_due` (Enterprise) se instala solo el puente
`pos_partner_performance_settle_due`, que deja de calcular la deuda de cada cliente: es la parte que
más tiempo ahorra (en staging, solo `total_due` del cliente por defecto de una tienda tardaba
37,7 s en cada apertura).
