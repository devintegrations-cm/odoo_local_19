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

- **Factura electrónica**: marcar una o varias órdenes (se ofrecen las confirmadas de los
  **últimos 12 meses** que no tienen factura ni una radicación en curso) y adjuntar el PDF y el
  **XML de la DIAN**. El XML es obligatorio para quien está obligado a facturar.
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

![Con observaciones: el flete supera el tope configurado sobre la mercancía](../static/description/13_portal_resultado_observaciones.png)

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
  qué método (por código, por IA o manual), con el **factor de unidad** cuando la factura viene en
  otra unidad que la orden. Si se cambia a mano la línea de la orden o el factor, hay que pulsar
  **Revalidar**; lo emparejado a mano se conserva. Los fletes quedan como **cargo adicional**.
- **Orden de compra**: las líneas de las órdenes al lado de la factura, con los subtotales y
  totales de las dos.
- **Datos extraídos**: emisor, adquiriente, número, fecha y totales leídos del XML.
- **Adjuntos**: el PDF y el XML tal como los subió el proveedor, con el ojo de vista previa.

![Pestaña Validación](../static/description/24_backend_validacion.png)

![Datos extraídos del XML](../static/description/26_backend_datos_extraidos.png)

Las pestañas *Líneas* (factor de unidad), *Orden de compra* y *Adjuntos* (vista previa) tienen su
paso a paso con capturas en el recorrido de la versión 19.0.1.3.0, al final.

## Crear la factura

Con la solicitud *Aprobada* o *Con observaciones*, **Crear factura** genera la factura de
proveedor en **borrador**:

- trae las líneas ligadas a la orden, y la orden queda *Facturada* en el momento;
- la referencia es el número del proveedor;
- la fecha contable es la fecha de la factura, no la de hoy;
- muestra el **CUFE / CUDE del proveedor**, con un botón para copiarlo y el enlace **Consultar en
  la DIAN** (en facturas y notas crédito de proveedor);
- adjunta el PDF y el XML;
- un flete va con el **producto de flete** y se liga a una línea de flete de la orden; si la orden
  no la tiene, se la agrega con la misma distribución analítica de la mercancía;
- con factor de unidad, la línea va en la unidad de la orden y el precio no se redondea, para que
  el subtotal sea exactamente el del XML.

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

**Aprobar a mano** una solicitud con observaciones y **generar los eventos RADIAN** de la factura
publicada: ver el recorrido de la versión 19.0.1.3.0, al final.

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

## Recorrido de la versión 19.0.1.3.0, paso a paso

Cada función nueva, con los pasos para repetirla en la interfaz y lo que se debe ver. Las pruebas
1 a 6 se hacen con un usuario **Responsable**, la 7 con un usuario del portal del proveedor y la 8
con un usuario de facturación cuyo contacto tenga los datos del firmante (ver *Datos del
firmante* en la configuración). Los números de las capturas son los de la base de pruebas: en
otra base cambian los documentos, no los pasos.

### Prueba 1: tope del flete

El flete que la orden no trae pasa si no supera el tope sobre la mercancía (los dos sin IVA); si lo
supera, la solicitud queda con observación.

- En *Compras › Configuración › Ajustes*, bloque *Portal de facturas de proveedor*, comprobar que
  hay **Producto de flete** y bajar **Tope del flete (%)** a 5. Guardar.
- Abrir una solicitud con flete por debajo del 10 % y por encima del 5 % de la mercancía (en la
  captura, un flete de 15.000 sobre 200.000: 7,5 %) y pulsar **Revalidar**.
- Resultado: la solicitud pasa a *Con observaciones*. En la pestaña *Validación*, la regla
  `EXTRA_CHARGES` dice el porcentaje real y el tope. El proveedor ve la misma observación en el
  portal.
- Devolver el tope a 10, guardar y revalidar: la solicitud vuelve a *Aprobada* y la regla del flete
  queda *Correcto*. Con el tope en 0 no hay límite.

![Portal › Facturas radicadas › detalle: Con observaciones porque el flete supera el tope](../static/description/13_portal_resultado_observaciones.png)

### Prueba 2: aprobar a mano una solicitud con observaciones

- Con la solicitud de la prueba 1 en *Con observaciones* (tope en 5), revisar la observación en la
  pestaña *Validación* y pulsar **Aprobar**.
- Resultado: la solicitud pasa a *Aprobada* y debajo del revisor aparecen **Aprobada por** y
  **Fecha de aprobación**. En el chatter queda quién la aprobó.
- Pulsar **Revalidar** (o *Volver a borrador*): los dos campos desaparecen y, si las reglas dejan
  otra vez observaciones, hay que volver a aprobar.
- Con un usuario solo **Validador** el botón *Aprobar* no aparece.
- Al terminar, devolver el tope a 10 y revalidar.

![Solicitud Con observaciones: regla EXTRA_CHARGES sobre el tope y botón Aprobar](../static/description/46_solicitud_observacion_flete_aprobar.png)

![Solicitud aprobada a mano: estado Aprobada, Aprobada por y Fecha de aprobación](../static/description/47_solicitud_aprobada_a_mano.png)

### Prueba 3: factor de unidad

Cuando el proveedor factura en otra unidad que la orden (bultos contra unidades, por ejemplo), la
línea guarda la unidad del XML y un factor. Cantidad y precio se comparan y se facturan en la
unidad de la orden.

- Abrir una solicitud cuya factura venga en otra unidad (en la captura, 1 BLT a 100.000 contra una
  orden en unidades), pestaña *Líneas y emparejamiento*. Con el botón de columnas de la lista
  (a la derecha de los títulos) mostrar *Unidad del documento* y *Precio en unidad de la orden*.
- Poner **Factor de unidad** 12 y pulsar **Revalidar**. La cantidad pasa a 12 y el precio a
  8.333,333333 en la unidad de la orden; el método queda *Manual*.
- Pulsar **Crear factura** y abrirla con el botón **Factura** del encabezado.
- Resultado: la línea de la factura dice 12 a 8.333,333333 y el subtotal es exactamente
  100.000,00, el del XML (antes daba 99.999,96). La fecha contable es la de la factura.
- Con la IA configurada, **Validar con IA** pone el factor solo cuando la confianza es alta y el
  precio convertido queda dentro de la tolerancia; las líneas emparejadas a mano no las toca.

![Líneas: 1 BLT en el XML, factor 12 y cantidad y precio en la unidad de la orden](../static/description/25_backend_lineas.png)

![Factura creada con el factor: 12 a 8.333,333333 y subtotal exacto](../static/description/48_factura_factor_unidad.png)

### Prueba 4: vista previa del PDF y del XML, y órdenes de compra

- Abrir una solicitud, pestaña **Adjuntos**. Al lado de cada archivo hay un **ojo**.
- Pulsar el ojo del XML: se abre el XML con sangría, sin descargarlo. El del PDF lo abre en el
  visor de Odoo.
- En una pantalla ancha, el PDF de la factura se ve al lado del formulario; en una angosta, en el
  chatter.
- El botón **Órdenes de compra** del encabezado abre la orden, o la lista si la factura cubre
  varias.

![Adjuntos: ojo de vista previa, PDF al lado del formulario y botón Órdenes de compra](../static/description/27_backend_adjuntos.png)

![Vista previa del XML de la DIAN](../static/description/49_vista_previa_xml.png)

### Prueba 5: pestaña Orden de compra

- En la misma solicitud, abrir la pestaña **Orden de compra**.
- Resultado: a la izquierda, subtotal y total de la factura; a la derecha, los de las órdenes;
  abajo, las líneas de las órdenes con cantidad, recibido, facturado y por facturar. En la captura
  los subtotales coinciden y los totales difieren por el flete, que la orden no trae.

![Pestaña Orden de compra: factura frente a órdenes](../static/description/50_pestana_orden_compra.png)

### Prueba 6: instructivo con los dos PDF

- Abrir la empresa proveedora, pestaña *Portal de proveedor*, y pulsar **Enviar instructivo del
  portal**.
- Resultado: el correo trae el paso a paso y **dos PDF** adjuntos (ver la captura del instructivo
  en la configuración). Abrir cada adjunto para revisarlo y cerrar con **Descartar** si solo se
  está probando.

### Prueba 7: órdenes de los últimos 12 meses en el portal

- Entrar al portal con un usuario del proveedor e ir a *Radicar facturas › Radicar factura*.
- Resultado: solo se ofrecen las órdenes con fecha de orden dentro de los últimos 12 meses. En la
  captura, P00036 (fecha de orden 29/11/2025) aparece y P00035 (29/09/2025) no, aunque las dos
  están esperando factura.
- Contabilidad registra una orden más vieja desde el backend, donde no hay filtro.

![Portal › Radicar factura: solo órdenes de los últimos 12 meses](../static/description/51_portal_ordenes_12_meses.png)

### Prueba 8: eventos RADIAN de receptor

Registra ante la DIAN el acuse de recibo (030), el recibo del bien (032) y la aceptación expresa
(033) de una factura de proveedor, en ese orden. No se generan al publicar: hay que pulsar el
botón.

- Abrir una factura de proveedor **publicada**, con **fecha de factura**, **CUFE / CUDE del
  proveedor**, en un diario marcado como *Eventos RADIAN de receptor* y sin eventos. El botón
  **Generar eventos RADIAN** aparece en el encabezado, junto a *Nota de crédito*.
- El botón no aparece en un borrador, sin CUFE o sin fecha, en una nota crédito de proveedor, en un
  diario sin la casilla o de documento soporte, ni si la factura ya tiene algún evento.

![Factura de proveedor publicada: botón Generar eventos RADIAN, fecha, diario y CUFE](../static/description/41_factura_boton_radian.png)

**Si faltan datos.** Con un firmante sin cargo o sin apellido, pulsar el botón muestra la lista de
lo que falta y no numera ningún evento. Completar el contacto y volver a pulsar. Lo mismo pasa si a
la compañía le falta el token de Edipo o el TestSetId.

![Faltan datos del firmante: apellido y cargo](../static/description/42_radian_faltan_datos_firmante.png)

**Resultado correcto.** Con todo completo, pulsar el botón:

- sale una notificación verde con los tres eventos generados y validados, y el mismo texto queda
  en el chatter;
- el botón desaparece;
- la pestaña **Eventos DIAN** muestra 030, 032 y 033 publicados.

![Eventos RADIAN generados: notificación verde y nota en el chatter](../static/description/43_radian_resultado_ok.png)

![Pestaña Eventos DIAN con 030, 032 y 033](../static/description/44_radian_pestana_eventos.png)

**Si la DIAN rechaza un evento.** Los que ya aceptó se conservan y los siguientes no se envían
(032 necesita el 030 y 033 el 032). La notificación sale amarilla y se queda fija hasta cerrarla;
dice qué evento falló y por qué, y lo mismo queda en el chatter. El botón no vuelve a aparecer: se
corrige la causa y los eventos que faltan se crean desde la pestaña *Eventos DIAN*.

![Rechazo del 032: aviso amarillo y el 030 conservado en Eventos DIAN](../static/description/45_radian_fallo_parcial.png)

### Sin captura

- **Validar con IA**: botón de la solicitud y acción *Validar con IA* de la lista para varias a la
  vez. Necesita el servicio de IA configurado en Ajustes.
- **Campos del portal por grupo**: un usuario sin Validador ni Responsable (un cajero del punto de
  venta, por ejemplo) abre un contacto, una orden o una factura sin error de acceso y sin ver los
  botones *Solicitudes* ni la pestaña *Portal de proveedor*.
- **Analítica del flete**: si la orden tiene distribución analítica, la línea de flete que se le
  agrega y la línea de la factura la llevan.
