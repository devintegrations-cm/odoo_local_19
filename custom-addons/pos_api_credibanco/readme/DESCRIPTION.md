Cobra con el **datáfono Credibanco** desde la pantalla de pago del Punto de Venta. El cajero agrega
el método de pago Credibanco, revisa el monto y pulsa **Enviar a Datafono**: el POS arma la trama
del protocolo Credibanco (total, IVA, IAC, propina, caja, número de transacción y cajero), la envía
al datáfono y, si el cliente aprueba, deja la línea pagada con el monto que realmente cobró el
terminal y su número de aprobación.

El navegador de la caja no habla con el datáfono directamente: lo hace a través de un **servicio
puente WebSocket** que corre en el equipo de la caja (contenedor `websocket-api-credibanco`), y ese
puente habla por TCP/IP con el datáfono.

Además del cobro, el módulo cubre lo que pasa cuando algo sale mal:

- **Venta sin respuesta**: si el datáfono no contesta o devuelve "sin respuesta final", la venta
  queda marcada como pendiente y el POS obliga a **recuperarla** antes de cobrar de nuevo, para no
  cobrar dos veces.
- **Anulación**: un pago aprobado se puede anular desde la misma pantalla de pago; la anulación se
  registra como una **línea de pago negativa**, igual que en Odoo 17.
- **Trazabilidad**: cada pago guarda la respuesta completa del datáfono y la muestra en la ficha
  del pago como un desglose legible (franquicia, recibo, terminal, cuotas...).

Se integra con el marco de terminales de pago del núcleo de Odoo 19
(`use_payment_terminal = 'credibanco'`), que es el que evita dos pagos electrónicos a la vez y
maneja los estados de la línea.
