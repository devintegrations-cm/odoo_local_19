Agrega al Punto de Venta el botón **Convenio To Plus** para canjear bonos (códigos promocionales,
cupones y tarjetas de regalo) pidiendo el **tipo y el número de documento** de quien canjea, y deja
el canje **registrado en la orden** para poder rastrearlo después.

El módulo no crea descuentos propios: aplica los programas de *Punto de venta › Productos ›
Descuentos y lealtad* con la lealtad nativa de Odoo (`pos_loyalty`). En las cajas donde está
activo, el botón reemplaza al «Enter Code» de Odoo.

- Formulario con tipo de documento, número y código, validado desde el primer **Validar**:
  - promociones con código: vigencia y lista de precios, en la caja;
  - cupones y tarjetas de regalo: consulta al servidor que **no gasta** el cupón;
  - en los tipos numéricos (NIT, CC, TI, TE, CE, NIUP), el número solo admite dígitos.
- El cupón se gasta recién al cobrar.
- Vista previa antes de aplicar: programa, valor (%, fijo o saldo de la tarjeta), vigencia y
  documento.
- Un código no se aplica dos veces en la misma orden. Si el cajero quitó la línea del descuento,
  el código se puede volver a aplicar sin que el cliente pierda el bono.
- Si la orden ya tenía otro código, se avisa en la vista previa y queda solo el nuevo.
- Pestaña **Descuento** en la orden con el programa, el código, el valor descontado, el estado
  del bono al canjear y el documento. El valor y el estado los calcula el servidor.
- Antes de abrir el formulario se revisa que `pos_loyalty` tenga la forma esperada: si una
  actualización de Odoo la cambia, el botón muestra un aviso en vez de aplicar descuentos a medias.
