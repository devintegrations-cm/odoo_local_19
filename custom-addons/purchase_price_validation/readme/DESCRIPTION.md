Controla el **precio unitario** con el que se compra y se recibe mercancía. Antes de confirmar una
orden de compra o de validar una recepción, compara el precio de cada producto con su **costo** y
detiene el proceso si encuentra alguno de estos casos:

- la diferencia entre el precio unitario y el costo supera el **porcentaje de variación** definido
  en el producto (10 % por defecto);
- el precio unitario es **0**.

Cuando eso pasa, se abre un asistente con una tabla de los productos afectados: variación
permitida, variación generada, costo y costo ingresado. Un **administrador de inventario** puede
confirmar igual; cualquier otro usuario solo puede cerrar el aviso y pedir la aprobación.

Existe para que un precio mal digitado, o una línea sin precio, no llegue al costo del inventario
sin que nadie lo revise.
