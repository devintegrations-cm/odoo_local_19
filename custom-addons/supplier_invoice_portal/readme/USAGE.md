## El proveedor, antes de radicar

Todo proveedor habilitado tiene que cargar **cámara de comercio, RUT y certificación bancaria**.
Mientras falte alguno, la entrada del portal (`/my`) muestra el aviso. **Radicar factura**, la
lista de solicitudes y el botón de la orden de compra muestran el mismo aviso y no dejan radicar.

![Portal › Mi cuenta: aviso de documentos faltantes y tarjeta Radicar facturas](../static/description/05_portal_inicio_aviso.png)

![Radicar sin los documentos: el formulario no se muestra](../static/description/06_portal_bloqueo_documentos.png)

En *Mi cuenta › Editar información* el proveedor completa su dirección con **código postal**
(Odoo lo exige para Colombia) y, si Jorels está instalado, sus **datos de facturación
electrónica**: tipo de régimen, tipo de responsabilidad, municipio y email de facturación.
También sube los tres documentos: PDF sin contraseña y de hasta 2 MB, arrastrando el archivo o
con clic. Los cuatro datos de facturación llevan asterisco de obligatorio, y los documentos que
todavía faltan también. Un documento ya cargado no hay que volver a subirlo para guardar.

- Si falta un campo obligatorio, el navegador no envía el formulario y marca el primero que está
  vacío.
- Un error del servidor sale arriba del formulario, y la zona del documento con error se pinta de
  rojo (por ejemplo, un RUT que no es PDF). Al elegir otro archivo se quita el rojo.
- Al guardar, los datos y los documentos quedan en la **empresa**, aunque los cargue un contacto
  hijo. En el chatter queda una nota "actualizó desde el portal".

![Mi cuenta con un error: el RUT no es PDF](../static/description/08_mi_cuenta_error.png)

![Mi cuenta completa: facturación electrónica y documentos cargados](../static/description/09_mi_cuenta_completa.png)

## El proveedor radica

Desde *Radicar facturas › Radicar factura*, o desde la orden de compra del portal con **Radicar
factura de esta orden**:

![Portal › orden de compra: Radicar factura de esta orden](../static/description/07_portal_orden_compra.png)

- **Factura electrónica**: marcar una o varias órdenes (se ofrecen las confirmadas que no tienen
  factura ni una radicación en curso) y adjuntar el PDF y el **XML de la DIAN**. El XML es
  obligatorio para quien está obligado a facturar.
- **Nota crédito** o **Nota débito**: elegir la factura que corrige (o dejar que se tome del XML) y
  adjuntar PDF y XML. La lista solo trae facturas ya publicadas. Si el XML apunta a una factura
  todavía en borrador, la solicitud queda *Con observaciones*.
- **Cuenta de cobro (documento soporte)**: solo para quien está marcado como no obligado a
  facturar. Se marcan las órdenes, se adjunta el PDF y se digitan número, fecha y valor total. No
  pide XML.
- En todos los casos el proveedor puede dejar una nota para contabilidad.

![Radicar una factura electrónica sobre una orden de compra](../static/description/10_portal_radicar_factura.png)

![Radicar una nota crédito: factura que afecta, PDF y XML](../static/description/14_portal_nota_credito.png)

![Cuenta de cobro de un proveedor no obligado a facturar](../static/description/15_portal_cuenta_de_cobro.png)

Al enviar, el proveedor ve el resultado de inmediato:

![Aprobada: pasó las validaciones y queda en cola de contabilidad](../static/description/11_portal_resultado_aprobada.png)

![Rechazada: total y cantidad mayores a lo pendiente de la orden](../static/description/12_portal_resultado_rechazada.png)

![Con observaciones: flete que no está en la orden de compra](../static/description/13_portal_resultado_observaciones.png)

En *Facturas radicadas* sigue el estado de cada documento. Si contabilidad rechaza una solicitud,
el motivo aparece en el detalle y le llega por correo:

![Portal › Facturas radicadas](../static/description/16_portal_lista_solicitudes.png)

![Detalle de una solicitud rechazada, con el motivo](../static/description/17_portal_detalle_rechazo.png)

Un proveedor sin la casilla **Puede radicar** no ve la tarjeta. Si entra a la dirección
directamente, ve este aviso:

![Proveedor no habilitado](../static/description/18_portal_no_habilitado.png)

## Contabilidad revisa

Menú *Compras › Solicitudes de pago de proveedor*. Por defecto la lista sale agrupada por estado.
El filtro **Por revisar** trae las *Aprobadas* y *Con observaciones*. Con **Mis revisiones** y
**Agrupar por revisor** se reparte el trabajo.

![Lista de solicitudes con su factura, revisor y estado](../static/description/19_backend_lista.png)

![Filtros Por revisar y Mis revisiones; agrupar por revisor](../static/description/20_backend_filtros.png)

Estados:

- **Borrador**: creada a mano en el backend, sin validar.
- **Validando**: se está procesando. Si se queda ahí, pulsar *Revalidar*.
- **Aprobada**: pasaron todas las reglas. Se puede crear la factura.
- **Con observaciones**: pasó, pero hay algo que revisar (flete, precio fuera de la tolerancia, línea sin
  emparejar, nota débito por aceptar).
- **Rechazada**: falló una regla dura o la rechazó el Responsable. El proveedor ya fue avisado.
- **Facturada**: ya tiene factura de proveedor.
- **Cancelada**: descartada por el Responsable.

Cuando llega una solicitud, **cada validador** recibe la actividad "Revisar solicitud de pago".
Quien la va a trabajar pulsa **Tomar revisión**: queda como *Revisor asignado*, las tareas de los
demás desaparecen y en el chatter queda una sola nota. Los otros usuarios ven el aviso **"En
revisión por …"**, que no los bloquea. Crear la factura, rechazar, aceptar una nota débito,
emparejar a mano o revalidar también asignan al usuario, si la solicitud no tenía revisor.

![Actividades del validador](../static/description/21_backend_actividades.png)

![Tomar revisión](../static/description/22_backend_tomar_revision.png)

![Aviso En revisión por, visto por otro usuario](../static/description/23_backend_en_revision_por.png)

Pestañas de la solicitud:

- **Validación**: cada regla con su resultado en español. Los errores rechazan; las observaciones
  solo avisan.
- **Líneas y emparejamiento**: a qué línea de la orden corresponde cada línea de la factura y por
  qué método (por código, por IA o manual). Si se cambia a mano la línea de la orden, hay que
  pulsar **Revalidar**; lo emparejado a mano se conserva. Los fletes quedan como **cargo
  adicional**.
- **Datos extraídos**: emisor, adquiriente, número, fecha y totales leídos del XML.
- **Adjuntos**: el PDF y el XML tal como los subió el proveedor.

![Pestaña Validación](../static/description/24_backend_validacion.png)

![Líneas: emparejamiento manual y cargo adicional](../static/description/25_backend_lineas.png)

![Datos extraídos del XML](../static/description/26_backend_datos_extraidos.png)

![Adjuntos de la solicitud](../static/description/27_backend_adjuntos.png)

## Crear la factura

Con la solicitud *Aprobada* o *Con observaciones*, **Crear factura** genera la factura de
proveedor en **borrador**:

- trae las líneas ligadas a la orden, y la orden queda *Facturada* en el momento;
- la referencia es el número del proveedor;
- muestra el **CUFE / CUDE del proveedor**, con un botón para copiarlo y el enlace **Consultar en
  la DIAN** (en facturas y notas crédito de proveedor);
- adjunta el PDF y el XML;
- un flete va con el **producto de flete** y se liga a una línea de flete de la orden; si la orden
  no la tiene, se la agrega.

Las actividades de revisión se cierran y el proveedor recibe el correo "factura registrada". La
factura se confirma por el flujo normal. Si se borra la factura borrador, la solicitud vuelve a
*Aprobada*.

![Factura borrador creada desde la solicitud: referencia, orden, PDF adjunto y CUFE con Consultar en la DIAN](../static/description/28_factura_borrador.png)

![Factura con la línea de flete](../static/description/29_factura_con_flete.png)

**Notas crédito y débito.** La nota se asocia a la factura que corrige y no cambia las cantidades
facturadas de la orden.

- La **nota crédito** genera un reembolso de proveedor en borrador que revierte esa factura. Si la
  línea de la orden tiene analítica, el reembolso la copia.
- La **nota débito** queda *Con observaciones* hasta que el Responsable pulse **Aceptar nota
  débito**. Recién entonces aparece *Crear factura*, que la liga a la factura original.

![Reembolso de proveedor generado por la nota crédito](../static/description/30_reembolso_nota_credito.png)

![Aceptar nota débito antes de crear la factura](../static/description/31_backend_aceptar_nota_debito.png)

**Cuenta de cobro.** Número, fecha y total los declara el proveedor; las líneas salen de lo
pendiente de sus órdenes. La factura se crea en el **diario de documento soporte**. Al
confirmarla, Jorels emite el documento soporte ante la DIAN; en la base local no lo hace, porque
no tiene resolución ni token.

![Cuenta de cobro registrada en el diario de documento soporte](../static/description/32_documento_soporte.png)

**Rechazar.** El Responsable rechaza una solicitud *Aprobada* o *Con observaciones* con
**Rechazar**. El motivo es obligatorio, le llega al proveedor y queda en el chatter.

![Asistente de rechazo con motivo](../static/description/33_backend_asistente_rechazo.png)

## Correos al proveedor

El proveedor recibe un correo cuando su documento queda en revisión, cuando no pasa las
validaciones, cuando contabilidad lo rechaza y cuando la factura queda registrada. Cada correo le
llega a la empresa y a la persona que radicó, también cuando es una persona natural sin empresa.

![Correo: la factura no pasó las validaciones](../static/description/34_correo_requiere_correccion.png)

![Correo: factura registrada](../static/description/35_correo_factura_registrada.png)

## Cierre de fin de mes

El último día hábil del mes, desde la hora de corte (12:00 por defecto), el portal muestra que la
radicación está cerrada y desde qué día se reabre. Solo cierra el portal: contabilidad puede seguir
creando solicitudes en el backend. Esta pantalla no se capturó, porque la prueba no se hizo en un
día de cierre.
