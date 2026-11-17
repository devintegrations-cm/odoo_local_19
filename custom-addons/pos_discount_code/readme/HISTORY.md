## 19.0.1.0.0

- Migración a Odoo 19. El botón pasa a las acciones de la orden (**⋮**) con el nombre
  **Convenio To Plus** y reemplaza al «Enter Code» de `pos_loyalty`.
- Los campos del canje se sincronizan con el modelo de la orden del POS; ya no se serializan a
  mano.
- El canje se valida al cobrar contra las líneas guardadas en el servidor: en 19 el POS solo envía
  las líneas nuevas o modificadas.
- Una orden en borrador conserva el canje aunque todavía no tenga línea de descuento (orden enviada
  a cocina antes de llegar a la compra mínima).
- Los tipos de documento llegan al POS con la configuración de la caja.

## 17.0.1.2.0

- Estado del bono guardado según la fecha del canje.
- Tipos de documento enviados al POS desde Python; se quitaron Registro Civil, PEP y PPT.
- Solo dígitos en los tipos numéricos (caja) y limpieza de separadores (servidor).
- Acceso a `pos_loyalty` concentrado en `loyalty_adapter.js`, con revisión de compatibilidad.
- Corregido: al recargar la caja, las órdenes abiertas perdían el código aplicado.

## 17.0.1.1.0

- Valor del descuento calculado en el servidor.
- Solo se registran bonos aplicados (programa, código y línea de recompensa).
- Fecha de canje en UTC.
- Un programa inexistente o un dato inválido ya no impiden sincronizar la orden.
- Cupones y tarjetas de regalo validados desde el primer clic.
- Se puede volver a aplicar un código cuyo descuento quitó el cajero.

## 17.0.1.0.0

- Versión inicial.
