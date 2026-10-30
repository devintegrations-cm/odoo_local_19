Los proveedores **radican en el portal de Odoo** sus facturas electrónicas DIAN, notas crédito,
notas débito y, si no están obligados a facturar, sus cuentas de cobro. Cada documento queda
asociado a una o varias órdenes de compra. Odoo lee el XML de la DIAN, revisa la factura contra la
orden y deja una **solicitud de pago** (`supplier.payment.request`, numeración `SPR/AAAA/NNNNN`)
con un veredicto: *Aprobada*, *Con observaciones* o *Rechazada*.

Contabilidad revisa la solicitud en *Compras › Solicitudes de pago de proveedor* y, con el botón
**Crear factura**, genera la factura de proveedor en **borrador**. Esa factura queda ligada a la
orden, con la referencia, el CUFE, la fecha y el PDF y el XML adjuntos. El módulo nunca
contabiliza solo: la factura se confirma y se paga por el flujo normal de contabilidad.

Para quién es:

- **Proveedor** (usuario del portal): carga sus documentos de empresa, radica y sigue el estado.
  Recibe un correo con cada cambio.
- **Validador** (contabilidad o compras): revisa, empareja líneas, toma la revisión y crea la
  factura.
- **Responsable** (*Compras: Administrador* lo es sin asignarlo): además configura, rechaza con
  motivo, acepta notas débito y habilita proveedores.

Lo que el módulo cubre:

- Solo radican los proveedores marcados como **Puede radicar facturas en el portal**, y solo sobre
  órdenes de los últimos 12 meses. Antes de radicar, cada uno tiene que cargar en *Mi cuenta* su
  cámara de comercio, su RUT y su certificación bancaria, y completar sus datos de facturación
  electrónica.
- Reglas automáticas: NIT del emisor y del adquiriente, CUFE repetido, estado de la orden, totales,
  impuestos, cantidades y precios contra lo pendiente de la orden, y tipo de documento.
- Fletes y envíos que la orden no trae: se marcan como **cargo adicional** y la factura los lleva
  con el producto de flete. Un flete que supera el **tope** sobre la mercancía queda como
  observación.
- Facturas en otra unidad que la orden: **factor de unidad** por línea, puesto a mano o propuesto
  por la IA.
- El Responsable puede **aprobar a mano** una solicitud con observaciones ya revisadas.
- Vista previa del PDF y del XML sin descargarlos, y las líneas de la orden al lado de la factura.
- Botón **Generar eventos RADIAN** en la factura de proveedor publicada: acuse de recibo, recibo
  del bien y aceptación expresa ante la DIAN (con la facturación electrónica de Jorels).
- Notas crédito (generan un reembolso) y notas débito (requieren aceptación) sobre una factura ya
  registrada.
- Cuenta de cobro de quien no está obligado a facturar: se registra en el diario de **documento
  soporte**.
- Una actividad de revisión por validador y el botón **Tomar revisión**.
- Cierre de la radicación el último día hábil del mes, desde la hora de corte.
