Impide que un **empleado no autorizado** reduzca o borre una línea de pedido del Punto de Venta
después de enviarla a cocina. Cada punto de venta tiene una lista de empleados autorizados. Si el
empleado que tiene la caja está en la lista, puede reducir o borrar líneas como siempre. Si no está,
el POS rechaza la acción con el aviso *Operacion no permitida*.

Existe para que un mesero no pueda quitar de la cuenta un producto que la cocina ya está preparando
sin pasar por el líder de tienda.

Cada línea enviada muestra su **cantidad ordenada** con el distintivo *En preparación* y dos botones
para restar o sumar una unidad. Aumentar la cantidad siempre está permitido. Con la lista vacía,
todos los empleados pueden reducir y borrar líneas.

Está pensado para puntos de venta de tipo restaurante (depende de `pos_restaurant`).
