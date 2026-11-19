No cambia nada en la pantalla del cajero. Al abrir la caja, el POS carga primero los clientes con
más órdenes **en esa caja** en los últimos 90 días y, después, el resto de contactos por nombre,
hasta completar la cantidad configurada.

Donde la lista de clientes está visible, se nota en el orden: aparecen primero los clientes de la
tienda (por ejemplo, sus convenios) y no los de otras tiendas. Al bajar en la lista se cargan más
con el mismo orden. La búsqueda (escribir y pulsar Enter) sigue buscando en **todos** los
contactos, como en el estándar.

El cliente por defecto de la caja (`pw_pos_default_customer`) se carga siempre al abrirla. No se
vuelve a agregar en las páginas siguientes de la lista: así cada página trae exactamente la cantidad
configurada y no se salta ningún cliente.
