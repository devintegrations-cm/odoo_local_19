Agrega al ticket del Punto de Venta **bloques de información adicional** configurables por tienda:
texto, texto legal, separadores, imágenes, códigos QR y códigos de barras. Cada punto de venta
tiene su propia lista de bloques, ordenable y con activación individual, y cada bloque se imprime
en una de tres posiciones del ticket: **cabecera**, **antes del pie** o **final del ticket**.

Tipos de bloque disponibles: texto libre, texto legal (letra más pequeña), separador, imagen, QR de
URL, QR de texto, código de barras, QR de reseña en Google, QR de WhatsApp, QR de WiFi, QR de
contacto (vCard) y QR de pago o propina.

Cada bloque puede limitarse por **vigencia** (fechas desde/hasta), **importe mínimo** del pedido y
**frecuencia** (uno de cada N pedidos). El contenido admite marcadores que se reemplazan al imprimir
con datos del pedido, como `{order_name}`, `{total}` o `{cashier}`.

Los QR y códigos de barras los genera el propio Odoo con el endpoint `/report/barcode`; no se usa
ninguna librería JavaScript externa. Las imágenes se incrustan en el ticket, así que se siguen
imprimiendo aunque la caja pierda la conexión, y si un código no se puede generar se imprime la
misma información en texto.
