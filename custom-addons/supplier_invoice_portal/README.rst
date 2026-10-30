===============================
Portal de facturas de proveedor
===============================

..
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! Generado por .claude/scripts/gen_readme.py          !!
   !! Los cambios se sobrescriben: editar readme/*.md     !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1| |badge2|

Los proveedores **radican en el portal de Odoo** sus facturas electrónicas DIAN, notas crédito,
notas débito y, si no están obligados a facturar, sus cuentas de cobro. Cada documento queda
asociado a una o varias órdenes de compra. Odoo lee el XML de la DIAN, revisa la factura contra la
orden y deja una **solicitud de pago** (``supplier.payment.request``, numeración ``SPR/AAAA/NNNNN``)
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

**Table of contents**

.. contents::
   :local:

Installation
============

Dependencias
------------

- **Obligatorias** (Odoo 19 Community): ``purchase``, ``account``, ``portal`` y ``mail``. Python: ``lxml``,
  que ya viene en la imagen de Odoo.
- **Jorels** (``l10n_co_edi_jorels``), opcional y fuera de ``depends``. Si está instalado, *Mi cuenta*
  pide al proveedor **tipo de régimen**, **tipo de responsabilidad**, **municipio** y **email de
  facturación**, todos obligatorios, y los guarda en la empresa. Además, la cuenta de cobro se
  emite como documento soporte electrónico al confirmar la factura. Sin Jorels esos campos no
  aparecen y nada falla.
- **pypdf**, opcional. Sirve para contar páginas y para detectar PDF con contraseña. Sin pypdf la
  contraseña se detecta por la marca ``/Encrypt`` del archivo: lo probamos en local, que no lo
  tiene, y un PDF cifrado fue rechazado. Odoo.sh trae pypdf. Está en ``requirements.txt`` del
  módulo; Odoo.sh solo lee el ``requirements.txt`` de la raíz del repositorio, así que la línea hay
  que copiarla allí. No está en ``external_dependencies`` a propósito: si faltara, bloquearía la
  instalación.

Instalar
--------

- Instalar **Portal de facturas de proveedor** desde *Aplicaciones* o con
  ``-i supplier_invoice_portal``.
- El módulo crea los grupos **Validador** y **Responsable**, la secuencia de solicitudes, las
  plantillas de correo y el menú *Compras › Solicitudes de pago de proveedor*. También agrega la
  pestaña **Portal de proveedor** en la ficha del contacto y el bloque de Ajustes.

Actualizar desde Odoo 17
------------------------

Los scripts de ``migrations/`` se ejecutan solos al actualizar y se pueden correr más de una vez.

- **17.0.1.1.0**: una solicitud pasa de una orden (``purchase_id``) a varias (``purchase_ids``); se
  copia la orden a la tabla nueva y se recrea la plantilla de correo de recibido.
- **17.0.1.2.0**: los documentos del proveedor dejan de ser campos binarios y pasan a ser adjuntos
  del contacto. Se reusa el adjunto existente y se le pone su nombre de archivo.
- **19.0.1.2.0**: el pre-migrate pasa a ``list`` las vistas del módulo que sigan como ``tree`` y
  renombra el xmlid de la lista si el nuevo no existe. El post-migrate reactiva las vistas del
  módulo que el upgrade haya dejado inactivas; la que no valide queda inactiva y se avisa en el
  log.

Configuration
=============

Ajustes del módulo
------------------

*Compras › Configuración › Ajustes*, bloque **Portal de facturas de proveedor**. Ese menú es de
*Administración / Ajustes*: un *Compras: Administrador* sin ese permiso no lo ve.

.. figure:: ../static/description/36_ajustes_modulo.png
   :alt: Compras › Configuración › Ajustes › Portal de facturas de proveedor: diarios, producto de flete, NIT, verificación de emisor y receptor, cierre de fin de mes y grupo validador

   Compras › Configuración › Ajustes › Portal de facturas de proveedor: diarios, producto de flete, NIT, verificación de emisor y receptor, cierre de fin de mes y grupo validador

- **Diario por defecto** (``spr.default_journal_id``): diario de compras donde se crean las
  facturas borrador.
- **Diario de documento soporte** (``spr.support_journal_id``): diario con la resolución DIAN de
  documento soporte. Ahí se registran las cuentas de cobro. Sin este diario, *Crear factura* no
  funciona para una cuenta de cobro.
- **Producto de flete** (``spr.freight_product_id``): producto de servicio para los fletes que la
  factura cobra y la orden no tiene. Sin él, *Crear factura* no funciona para una factura con
  flete.
- **Tope del flete (%)** (``spr.freight_max_pct``): aparece con el producto de flete. Si los fletes de
  la factura superan ese porcentaje del subtotal de la mercancía, la solicitud queda *Con
  observaciones*. Se comparan las dos bases, sin IVA. Por defecto 10 %; 0 = sin tope.
- **Tolerancia de montos**: diferencia admitida entre la factura y lo pendiente de la orden. Pasa
  si está dentro del porcentaje **o** del monto absoluto. Por defecto 0,5 % o 1.000. La misma
  tolerancia porcentual vale para el **precio unitario** de cada línea: es la regla de negocio
  vigente. Un precio de 12.050 contra 12.000 de la orden (0,42 %) pasa sin observación.
- **NIT de la compañía**: dejarlo vacío si el NIT está bien puesto en la ficha de la compañía.
- **Verificar emisor y receptor**: activo por defecto. Compara el NIT del emisor con el proveedor
  y el del adquiriente con la compañía.
- **Cierre de radicación de fin de mes**: activo por defecto, con **hora de corte** a las 12:00.
  El último día hábil del mes, desde esa hora, el portal no recibe documentos hasta el día 1. Tiene
  en cuenta los festivos de Colombia.
- **Grupo validador**: el grupo cuyos usuarios reciben la actividad de revisión.
- **IVA como producto**: apagado por defecto. Activo, las líneas van con el impuesto exento y el
  IVA entra como una línea del producto de mayor valor IVA.
- **Verificar el CUFE en el catálogo DIAN**: apagado por defecto, porque la DIAN pide captcha.
- **OCR del PDF**, **Emparejamiento por IA** y **Conexión de prueba por CLI**: servicios externos
  opcionales. Ver ``README.md`` del módulo.

El **tope del flete** aparece debajo del producto de flete, solo cuando hay producto elegido. Con
el tope en 10 %, un flete de 15.000 sobre una mercancía de 200.000 (7,5 %) pasa; con el tope en
5 %, la misma factura queda *Con observaciones*.

.. figure:: ../static/description/39_ajustes_tope_flete.png
   :alt: Compras › Configuración › Ajustes › Portal de facturas de proveedor: producto de flete y Tope del flete (%)

   Compras › Configuración › Ajustes › Portal de facturas de proveedor: producto de flete y Tope del flete (%)

Diario para los eventos RADIAN
------------------------------

Solo con la facturación electrónica de Jorels instalada. En *Facturación › Configuración ›
Diarios* (*Contabilidad › Configuración › Diarios* con la contabilidad completa), abrir el diario de
compras de las facturas electrónicas de proveedores y marcar **Eventos RADIAN de receptor**, en la
pestaña *Asientos contables*. La casilla la ve el administrador de contabilidad.

.. figure:: ../static/description/38_diario_eventos_radian.png
   :alt: Facturación › Configuración › Diarios › Facturas de Proveedores: casilla Eventos RADIAN de receptor

   Facturación › Configuración › Diarios › Facturas de Proveedores: casilla Eventos RADIAN de receptor

- Las facturas publicadas en ese diario muestran el botón **Generar eventos RADIAN**. En un diario
  sin la casilla el botón no aparece.
- Si hay varios diarios de compras (gastos, importaciones…), se marca solo el de las facturas
  electrónicas. No se marca por nombre ni se deduce: es un paso de la puesta en producción.
- No se puede marcar en un diario que no sea de compras ni en el de documento soporte: Odoo no deja
  guardar. Una factura en un diario con resolución de documento soporte nunca muestra el botón,
  aunque el diario esté marcado.
- La compañía necesita la facturación electrónica activa, el token de Edipo y, en ambiente de
  pruebas, el TestSetId (*Ajustes › Facturación electrónica*).

Datos del firmante
~~~~~~~~~~~~~~~~~~

Los eventos salen firmados por quien pulsa el botón. En su contacto (*Ajustes › Usuarios*, abrir
el usuario y su contacto, o *Contactos*) tienen que estar:

- **Puesto de trabajo**: es el cargo del firmante.
- **Número de identificación**: tipo y número reales. El 222222222222 que Jorels pone a los
  usuarios nuevos no sirve.
- **Primer nombre** y **Apellido**, en la pestaña *Información postal*.

.. figure:: ../static/description/40_firmante_radian.png
   :alt: Contacto del usuario firmante: puesto de trabajo, tipo y número de identificación, primer nombre y apellido

   Contacto del usuario firmante: puesto de trabajo, tipo y número de identificación, primer nombre y apellido

Si falta alguno, el botón no envía nada y muestra la lista de lo que falta (ver *Eventos RADIAN* en
el uso).

Habilitar un proveedor
----------------------

Se hace en la ficha de la **empresa**, o de la persona natural que no pertenece a ninguna empresa.
La ficha debe tener el NIT. En un contacto hijo la pestaña no aparece: ese contacto radica a
nombre de su empresa. La pestaña la ven solo los usuarios del grupo **Responsable**.

.. figure:: ../static/description/01_proveedor_habilitado.png
   :alt: Contactos › proveedor › Portal de proveedor: casillas, documentos y botón del instructivo

   Contactos › proveedor › Portal de proveedor: casillas, documentos y botón del instructivo

- **Puede radicar facturas en el portal** (``portal_invoice_enabled``). Sin esta casilla, el
  proveedor entra al portal pero no ve *Radicar facturas*.
- **No obligado a facturar (documento soporte)** (``spr_support_document``). Marcarla solo para
  quien radica cuentas de cobro: le agrega el tipo *Cuenta de cobro* y no le pide XML.
- **Documentos del proveedor**: cámara de comercio, RUT y certificación bancaria. Normalmente los
  carga el proveedor desde *Mi cuenta*. Desde el backend se adjunta el PDF en el chatter y se
  elige en el campo. Debajo se ve la vista previa de cada uno.
- La pestaña **Facturación electrónica** (Jorels) muestra los datos que el proveedor completa en
  *Mi cuenta*.

.. figure:: ../static/description/04_datos_jorels.png
   :alt: Contacto › Facturación electrónica: régimen, responsabilidad, municipio y email que completa el proveedor

   Contacto › Facturación electrónica: régimen, responsabilidad, municipio y email que completa el proveedor

Dar acceso al portal
--------------------

- En la empresa, pestaña *Contactos*, crear un contacto hijo con correo para cada persona que va a
  radicar. Luego, en ese contacto, ir a *Acción › Otorgar acceso al portal*. Es el asistente
  estándar de Odoo y requiere permisos de administración: un *Compras: Administrador* recibe
  "No tiene suficientes permisos".

.. figure:: ../static/description/37_otorgar_acceso_portal.png
   :alt: Contacto › Acción › Otorgar acceso al portal: asistente estándar de Odoo para dar acceso al contacto que va a radicar

   Contacto › Acción › Otorgar acceso al portal: asistente estándar de Odoo para dar acceso al contacto que va a radicar

- Odoo envía la invitación y el usuario define su clave. Si hay varias bases sin ``dbfilter``, el
  enlace hay que abrirlo después de entrar a ``/web/login?db=<base>``.

.. figure:: ../static/description/03_invitacion_portal.png
   :alt: Invitación al portal que recibe el contacto

   Invitación al portal que recibe el contacto

- Pulsar **Enviar instructivo del portal** en la ficha de la empresa, pestaña *Portal de
  proveedor*. Se abre el correo con el paso a paso y **dos PDF ya adjuntos**: el instructivo
  generado con el nombre y el NIT de la compañía, la hora de corte y, para quien no está obligado a
  facturar, la cuenta de cobro en lugar del XML; y la guía del portal. Solo hay que revisar los
  destinatarios y enviar.

.. figure:: ../static/description/02_instructivo.png
   :alt: Contacto › Portal de proveedor › Enviar instructivo del portal: destinatario, los dos PDF adjuntos y Enviar

   Contacto › Portal de proveedor › Enviar instructivo del portal: destinatario, los dos PDF adjuntos y Enviar

Permisos
--------

- **Validador**: ve las solicitudes, valida, empareja líneas a mano, toma la revisión y crea la
  factura borrador.
- **Responsable**: lo anterior, más rechazar, aprobar a mano una solicitud con observaciones,
  aceptar notas débito, devolver a borrador, cancelar y habilitar proveedores. *Compras:
  Administrador* es Responsable sin asignarlo.
- **Generar eventos RADIAN**: cualquier usuario de facturación que pueda publicar facturas, aunque
  no tenga el grupo de facturación electrónica de Jorels.
- Los botones y pestañas del portal en contactos, órdenes y facturas (*Solicitudes*, *Portal de
  proveedor*, documentos) solo los ven Validador y Responsable. Un usuario sin esos grupos, como un
  cajero del punto de venta, lee el contacto sin errores de acceso.
- Los grupos se asignan en la ficha del usuario, sección *Portal de facturas de proveedor*.
- **Requisito con Jorels: los validadores deben tener *Facturación electrónica / Usuario*.** El
  personal de contabilidad y compras que revisa solicitudes tiene ese acceso. Sin él, *Crear
  factura* sí crea el borrador, pero al abrirlo Odoo muestra "Error de acceso … Eventos del
  Radian", y tampoco se puede confirmar.
- El proveedor (usuario del portal) solo ve las solicitudes de su empresa.

Usage
=====

El proveedor, antes de radicar
------------------------------

Todo proveedor habilitado tiene que cargar **cámara de comercio, RUT y certificación bancaria**.
Mientras falte alguno, la entrada del portal (``/my``) muestra el aviso. **Radicar factura**, la
lista de solicitudes y el botón de la orden de compra muestran el mismo aviso y no dejan radicar.

.. figure:: ../static/description/05_portal_inicio_aviso.png
   :alt: Portal › Mi cuenta: aviso de documentos faltantes y tarjeta Radicar facturas

   Portal › Mi cuenta: aviso de documentos faltantes y tarjeta Radicar facturas

.. figure:: ../static/description/06_portal_bloqueo_documentos.png
   :alt: Radicar sin los documentos: el formulario no se muestra

   Radicar sin los documentos: el formulario no se muestra

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

.. figure:: ../static/description/08_mi_cuenta_error.png
   :alt: Mi cuenta con un error: el RUT no es PDF

   Mi cuenta con un error: el RUT no es PDF

.. figure:: ../static/description/09_mi_cuenta_completa.png
   :alt: Mi cuenta completa: facturación electrónica y documentos cargados

   Mi cuenta completa: facturación electrónica y documentos cargados

El proveedor radica
-------------------

Desde *Radicar facturas › Radicar factura*, o desde la orden de compra del portal con **Radicar
factura de esta orden**:

.. figure:: ../static/description/07_portal_orden_compra.png
   :alt: Portal › orden de compra: Radicar factura de esta orden

   Portal › orden de compra: Radicar factura de esta orden

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

.. figure:: ../static/description/10_portal_radicar_factura.png
   :alt: Radicar una factura electrónica sobre una orden de compra

   Radicar una factura electrónica sobre una orden de compra

.. figure:: ../static/description/14_portal_nota_credito.png
   :alt: Radicar una nota crédito: factura que afecta, PDF y XML

   Radicar una nota crédito: factura que afecta, PDF y XML

.. figure:: ../static/description/15_portal_cuenta_de_cobro.png
   :alt: Cuenta de cobro de un proveedor no obligado a facturar

   Cuenta de cobro de un proveedor no obligado a facturar

Al enviar, el proveedor ve el resultado de inmediato:

.. figure:: ../static/description/11_portal_resultado_aprobada.png
   :alt: Aprobada: pasó las validaciones y queda en cola de contabilidad

   Aprobada: pasó las validaciones y queda en cola de contabilidad

.. figure:: ../static/description/12_portal_resultado_rechazada.png
   :alt: Rechazada: total y cantidad mayores a lo pendiente de la orden

   Rechazada: total y cantidad mayores a lo pendiente de la orden

.. figure:: ../static/description/13_portal_resultado_observaciones.png
   :alt: Con observaciones: el flete supera el tope configurado sobre la mercancía

   Con observaciones: el flete supera el tope configurado sobre la mercancía

En *Facturas radicadas* sigue el estado de cada documento. Si contabilidad rechaza una solicitud,
el motivo aparece en el detalle y le llega por correo:

.. figure:: ../static/description/16_portal_lista_solicitudes.png
   :alt: Portal › Facturas radicadas

   Portal › Facturas radicadas

.. figure:: ../static/description/17_portal_detalle_rechazo.png
   :alt: Detalle de una solicitud rechazada, con el motivo

   Detalle de una solicitud rechazada, con el motivo

Un proveedor sin la casilla **Puede radicar** no ve la tarjeta. Si entra a la dirección
directamente, ve este aviso:

.. figure:: ../static/description/18_portal_no_habilitado.png
   :alt: Proveedor no habilitado

   Proveedor no habilitado

Contabilidad revisa
-------------------

Menú *Compras › Solicitudes de pago de proveedor*. Por defecto la lista sale agrupada por estado.
El filtro **Por revisar** trae las *Aprobadas* y *Con observaciones*. Con **Mis revisiones** y
**Agrupar por revisor** se reparte el trabajo.

.. figure:: ../static/description/19_backend_lista.png
   :alt: Lista de solicitudes con su factura, revisor y estado

   Lista de solicitudes con su factura, revisor y estado

.. figure:: ../static/description/20_backend_filtros.png
   :alt: Filtros Por revisar y Mis revisiones; agrupar por revisor

   Filtros Por revisar y Mis revisiones; agrupar por revisor

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

.. figure:: ../static/description/21_backend_actividades.png
   :alt: Actividades del validador

   Actividades del validador

.. figure:: ../static/description/22_backend_tomar_revision.png
   :alt: Tomar revisión

   Tomar revisión

.. figure:: ../static/description/23_backend_en_revision_por.png
   :alt: Aviso En revisión por, visto por otro usuario

   Aviso En revisión por, visto por otro usuario

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

.. figure:: ../static/description/24_backend_validacion.png
   :alt: Pestaña Validación

   Pestaña Validación

.. figure:: ../static/description/26_backend_datos_extraidos.png
   :alt: Datos extraídos del XML

   Datos extraídos del XML

Las pestañas *Líneas* (factor de unidad), *Orden de compra* y *Adjuntos* (vista previa) tienen su
paso a paso con capturas en el recorrido de la versión 19.0.1.3.0, al final.

Crear la factura
----------------

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

.. figure:: ../static/description/28_factura_borrador.png
   :alt: Factura borrador creada desde la solicitud: referencia, orden, PDF adjunto y CUFE con Consultar en la DIAN

   Factura borrador creada desde la solicitud: referencia, orden, PDF adjunto y CUFE con Consultar en la DIAN

.. figure:: ../static/description/29_factura_con_flete.png
   :alt: Factura con la línea de flete

   Factura con la línea de flete

**Notas crédito y débito.** La nota se asocia a la factura que corrige y no cambia las cantidades
facturadas de la orden.

- La **nota crédito** genera un reembolso de proveedor en borrador que revierte esa factura. Si la
  línea de la orden tiene analítica, el reembolso la copia.
- La **nota débito** queda *Con observaciones* hasta que el Responsable pulse **Aceptar nota
  débito**. Recién entonces aparece *Crear factura*, que la liga a la factura original.

.. figure:: ../static/description/30_reembolso_nota_credito.png
   :alt: Reembolso de proveedor generado por la nota crédito

   Reembolso de proveedor generado por la nota crédito

.. figure:: ../static/description/31_backend_aceptar_nota_debito.png
   :alt: Aceptar nota débito antes de crear la factura

   Aceptar nota débito antes de crear la factura

**Cuenta de cobro.** Número, fecha y total los declara el proveedor; las líneas salen de lo
pendiente de sus órdenes. La factura se crea en el **diario de documento soporte**. Al
confirmarla, Jorels emite el documento soporte ante la DIAN; en la base local no lo hace, porque
no tiene resolución ni token.

.. figure:: ../static/description/32_documento_soporte.png
   :alt: Cuenta de cobro registrada en el diario de documento soporte

   Cuenta de cobro registrada en el diario de documento soporte

**Rechazar.** El Responsable rechaza una solicitud *Aprobada* o *Con observaciones* con
**Rechazar**. El motivo es obligatorio, le llega al proveedor y queda en el chatter.

.. figure:: ../static/description/33_backend_asistente_rechazo.png
   :alt: Asistente de rechazo con motivo

   Asistente de rechazo con motivo

**Aprobar a mano** una solicitud con observaciones y **generar los eventos RADIAN** de la factura
publicada: ver el recorrido de la versión 19.0.1.3.0, al final.

Correos al proveedor
--------------------

El proveedor recibe un correo cuando su documento queda en revisión, cuando no pasa las
validaciones, cuando contabilidad lo rechaza y cuando la factura queda registrada. Cada correo le
llega a la empresa y a la persona que radicó, también cuando es una persona natural sin empresa.

.. figure:: ../static/description/34_correo_requiere_correccion.png
   :alt: Correo: la factura no pasó las validaciones

   Correo: la factura no pasó las validaciones

.. figure:: ../static/description/35_correo_factura_registrada.png
   :alt: Correo: factura registrada

   Correo: factura registrada

Cierre de fin de mes
--------------------

El último día hábil del mes, desde la hora de corte (12:00 por defecto), el portal muestra que la
radicación está cerrada y desde qué día se reabre. Solo cierra el portal: contabilidad puede seguir
creando solicitudes en el backend. Esta pantalla no se capturó, porque la prueba no se hizo en un
día de cierre.

Recorrido de la versión 19.0.1.3.0, paso a paso
-----------------------------------------------

Cada función nueva, con los pasos para repetirla en la interfaz y lo que se debe ver. Las pruebas
1 a 6 se hacen con un usuario **Responsable**, la 7 con un usuario del portal del proveedor y la 8
con un usuario de facturación cuyo contacto tenga los datos del firmante (ver *Datos del
firmante* en la configuración). Los números de las capturas son los de la base de pruebas: en
otra base cambian los documentos, no los pasos.

Prueba 1: tope del flete
~~~~~~~~~~~~~~~~~~~~~~~~

El flete que la orden no trae pasa si no supera el tope sobre la mercancía (los dos sin IVA); si lo
supera, la solicitud queda con observación.

- En *Compras › Configuración › Ajustes*, bloque *Portal de facturas de proveedor*, comprobar que
  hay **Producto de flete** y bajar **Tope del flete (%)** a 5. Guardar.
- Abrir una solicitud con flete por debajo del 10 % y por encima del 5 % de la mercancía (en la
  captura, un flete de 15.000 sobre 200.000: 7,5 %) y pulsar **Revalidar**.
- Resultado: la solicitud pasa a *Con observaciones*. En la pestaña *Validación*, la regla
  ``EXTRA_CHARGES`` dice el porcentaje real y el tope. El proveedor ve la misma observación en el
  portal.
- Devolver el tope a 10, guardar y revalidar: la solicitud vuelve a *Aprobada* y la regla del flete
  queda *Correcto*. Con el tope en 0 no hay límite.

.. figure:: ../static/description/13_portal_resultado_observaciones.png
   :alt: Portal › Facturas radicadas › detalle: Con observaciones porque el flete supera el tope

   Portal › Facturas radicadas › detalle: Con observaciones porque el flete supera el tope

Prueba 2: aprobar a mano una solicitud con observaciones
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Con la solicitud de la prueba 1 en *Con observaciones* (tope en 5), revisar la observación en la
  pestaña *Validación* y pulsar **Aprobar**.
- Resultado: la solicitud pasa a *Aprobada* y debajo del revisor aparecen **Aprobada por** y
  **Fecha de aprobación**. En el chatter queda quién la aprobó.
- Pulsar **Revalidar** (o *Volver a borrador*): los dos campos desaparecen y, si las reglas dejan
  otra vez observaciones, hay que volver a aprobar.
- Con un usuario solo **Validador** el botón *Aprobar* no aparece.
- Al terminar, devolver el tope a 10 y revalidar.

.. figure:: ../static/description/46_solicitud_observacion_flete_aprobar.png
   :alt: Solicitud Con observaciones: regla EXTRA_CHARGES sobre el tope y botón Aprobar

   Solicitud Con observaciones: regla EXTRA_CHARGES sobre el tope y botón Aprobar

.. figure:: ../static/description/47_solicitud_aprobada_a_mano.png
   :alt: Solicitud aprobada a mano: estado Aprobada, Aprobada por y Fecha de aprobación

   Solicitud aprobada a mano: estado Aprobada, Aprobada por y Fecha de aprobación

Prueba 3: factor de unidad
~~~~~~~~~~~~~~~~~~~~~~~~~~

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

.. figure:: ../static/description/25_backend_lineas.png
   :alt: Líneas: 1 BLT en el XML, factor 12 y cantidad y precio en la unidad de la orden

   Líneas: 1 BLT en el XML, factor 12 y cantidad y precio en la unidad de la orden

.. figure:: ../static/description/48_factura_factor_unidad.png
   :alt: Factura creada con el factor: 12 a 8.333,333333 y subtotal exacto

   Factura creada con el factor: 12 a 8.333,333333 y subtotal exacto

Prueba 4: vista previa del PDF y del XML, y órdenes de compra
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Abrir una solicitud, pestaña **Adjuntos**. Al lado de cada archivo hay un **ojo**.
- Pulsar el ojo del XML: se abre el XML con sangría, sin descargarlo. El del PDF lo abre en el
  visor de Odoo.
- En una pantalla ancha, el PDF de la factura se ve al lado del formulario; en una angosta, en el
  chatter.
- El botón **Órdenes de compra** del encabezado abre la orden, o la lista si la factura cubre
  varias.

.. figure:: ../static/description/27_backend_adjuntos.png
   :alt: Adjuntos: ojo de vista previa, PDF al lado del formulario y botón Órdenes de compra

   Adjuntos: ojo de vista previa, PDF al lado del formulario y botón Órdenes de compra

.. figure:: ../static/description/49_vista_previa_xml.png
   :alt: Vista previa del XML de la DIAN

   Vista previa del XML de la DIAN

Prueba 5: pestaña Orden de compra
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- En la misma solicitud, abrir la pestaña **Orden de compra**.
- Resultado: a la izquierda, subtotal y total de la factura; a la derecha, los de las órdenes;
  abajo, las líneas de las órdenes con cantidad, recibido, facturado y por facturar. En la captura
  los subtotales coinciden y los totales difieren por el flete, que la orden no trae.

.. figure:: ../static/description/50_pestana_orden_compra.png
   :alt: Pestaña Orden de compra: factura frente a órdenes

   Pestaña Orden de compra: factura frente a órdenes

Prueba 6: instructivo con los dos PDF
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Abrir la empresa proveedora, pestaña *Portal de proveedor*, y pulsar **Enviar instructivo del
  portal**.
- Resultado: el correo trae el paso a paso y **dos PDF** adjuntos (ver la captura del instructivo
  en la configuración). Abrir cada adjunto para revisarlo y cerrar con **Descartar** si solo se
  está probando.

Prueba 7: órdenes de los últimos 12 meses en el portal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Entrar al portal con un usuario del proveedor e ir a *Radicar facturas › Radicar factura*.
- Resultado: solo se ofrecen las órdenes con fecha de orden dentro de los últimos 12 meses. En la
  captura, P00036 (fecha de orden 29/11/2025) aparece y P00035 (29/09/2025) no, aunque las dos
  están esperando factura.
- Contabilidad registra una orden más vieja desde el backend, donde no hay filtro.

.. figure:: ../static/description/51_portal_ordenes_12_meses.png
   :alt: Portal › Radicar factura: solo órdenes de los últimos 12 meses

   Portal › Radicar factura: solo órdenes de los últimos 12 meses

Prueba 8: eventos RADIAN de receptor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Registra ante la DIAN el acuse de recibo (030), el recibo del bien (032) y la aceptación expresa
(033) de una factura de proveedor, en ese orden. No se generan al publicar: hay que pulsar el
botón.

- Abrir una factura de proveedor **publicada**, con **fecha de factura**, **CUFE / CUDE del
  proveedor**, en un diario marcado como *Eventos RADIAN de receptor* y sin eventos. El botón
  **Generar eventos RADIAN** aparece en el encabezado, junto a *Nota de crédito*.
- El botón no aparece en un borrador, sin CUFE o sin fecha, en una nota crédito de proveedor, en un
  diario sin la casilla o de documento soporte, ni si la factura ya tiene algún evento.

.. figure:: ../static/description/41_factura_boton_radian.png
   :alt: Factura de proveedor publicada: botón Generar eventos RADIAN, fecha, diario y CUFE

   Factura de proveedor publicada: botón Generar eventos RADIAN, fecha, diario y CUFE

**Si faltan datos.** Con un firmante sin cargo o sin apellido, pulsar el botón muestra la lista de
lo que falta y no numera ningún evento. Completar el contacto y volver a pulsar. Lo mismo pasa si a
la compañía le falta el token de Edipo o el TestSetId.

.. figure:: ../static/description/42_radian_faltan_datos_firmante.png
   :alt: Faltan datos del firmante: apellido y cargo

   Faltan datos del firmante: apellido y cargo

**Resultado correcto.** Con todo completo, pulsar el botón:

- sale una notificación verde con los tres eventos generados y validados, y el mismo texto queda
  en el chatter;
- el botón desaparece;
- la pestaña **Eventos DIAN** muestra 030, 032 y 033 publicados.

.. figure:: ../static/description/43_radian_resultado_ok.png
   :alt: Eventos RADIAN generados: notificación verde y nota en el chatter

   Eventos RADIAN generados: notificación verde y nota en el chatter

.. figure:: ../static/description/44_radian_pestana_eventos.png
   :alt: Pestaña Eventos DIAN con 030, 032 y 033

   Pestaña Eventos DIAN con 030, 032 y 033

**Si la DIAN rechaza un evento.** Los que ya aceptó se conservan y los siguientes no se envían
(032 necesita el 030 y 033 el 032). La notificación sale amarilla y se queda fija hasta cerrarla;
dice qué evento falló y por qué, y lo mismo queda en el chatter. El botón no vuelve a aparecer: se
corrige la causa y los eventos que faltan se crean desde la pestaña *Eventos DIAN*.

.. figure:: ../static/description/45_radian_fallo_parcial.png
   :alt: Rechazo del 032: aviso amarillo y el 030 conservado en Eventos DIAN

   Rechazo del 032: aviso amarillo y el 030 conservado en Eventos DIAN

Sin captura
~~~~~~~~~~~

- **Validar con IA**: botón de la solicitud y acción *Validar con IA* de la lista para varias a la
  vez. Necesita el servicio de IA configurado en Ajustes.
- **Campos del portal por grupo**: un usuario sin Validador ni Responsable (un cajero del punto de
  venta, por ejemplo) abre un contacto, una orden o una factura sin error de acceso y sin ver los
  botones *Solicitudes* ni la pestaña *Portal de proveedor*.
- **Analítica del flete**: si la orden tiene distribución analítica, la línea de flete que se le
  agrega y la línea de la factura la llevan.

Known issues / Roadmap
======================

Hallazgos abiertos de la prueba en navegador (Odoo 19, 2026-10-02)
------------------------------------------------------------------

- **Mi cuenta: el navegador avisa un campo a la vez.** Odoo 19 valida primero en el navegador
  (``reportValidity``): marca el primer campo obligatorio vacío y no muestra la lista de errores en
  rojo. La lista del servidor aparece solo en los errores que el navegador no detecta, como un
  archivo que no es PDF.

Verificar en staging
--------------------

- **Documento soporte electrónico**: confirmar una cuenta de cobro en el diario de documento
  soporte y comprobar que Jorels lo emite ante la DIAN. En local la factura queda *Registrada*
  con la advertencia "NO ha sido validado con la DIAN".
- **Municipios de Jorels**: el selector de *Mi cuenta* tiene unas 1.100 opciones; revisar que sea
  usable con los datos reales.
- **pypdf**: comprobar que esté instalado (Odoo.sh lo trae) y que la línea de
  ``requirements.txt`` esté en la raíz del repositorio. En local no está, y un PDF con contraseña se
  rechazó igual, por la marca ``/Encrypt``.
- **Analítica en notas**: la orden de la prueba no tenía analítica. Falta ver un reembolso cuya
  orden sí la tenga.
- **Eventos RADIAN ante la DIAN real**: generar los eventos de una factura de proveedor con el
  token de Edipo y el TestSetId de staging (o en producción) y un firmante con documento, nombre,
  apellido y cargo reales. Confirmar que quien los genera no necesita el grupo de facturación
  electrónica de Jorels y que la DIAN acepta los tres.
- **Diario de RADIAN en producción**: marcar *Eventos RADIAN de receptor* solo en el diario de
  facturas electrónicas de proveedores (``CHECKLIST_PRODUCCION.md``).

Pendiente de documentar
-----------------------

- **Pantalla de cierre de fin de mes** en el portal: solo se ve el último día hábil del mes,
  después de la hora de corte.
- **Icono** ``static/description/icon.png`` de 100×100: falta y necesita arte.
- **Validar con IA**: falta la captura del botón y de la acción de la lista; necesita el servicio de
  IA configurado.
- **Capturas del backend anteriores a 19.0.1.3.0** (lista, filtros, actividades, tomar revisión,
  validación, datos extraídos, factura, notas, documento soporte y rechazo): son de Odoo 19, pero
  todavía no muestran los botones *Validar con IA*, *Aprobar* y *Órdenes de compra* ni la pestaña
  *Orden de compra*. Hay que recapturarlas.

Límites conocidos
-----------------

- **Los eventos RADIAN no se generan al publicar**: hay que pulsar el botón en cada factura. Si un
  evento falla, el botón ya no vuelve a aparecer y los que faltan se crean desde *Eventos DIAN*.
- **Una orden de más de 12 meses no se radica por el portal**: la registra contabilidad en el
  backend.
- **La tolerancia porcentual (0,5 % por defecto) vale también para el precio unitario.** Es la
  regla de negocio vigente: un precio de 12.050 contra 12.000 (0,42 %) no deja la observación
  ``PRICE_UNIT_MISMATCH``.
- **Con Jorels, los validadores necesitan *Facturación electrónica / Usuario*** para abrir y
  confirmar las facturas que crea el módulo. Ver *Permisos* en la configuración.

- La numeración ``SPR/…`` es interna. La factura usa la secuencia del diario y, en el documento
  soporte, la resolución DIAN.
- Una orden con una radicación en curso (no rechazada ni cancelada), o que ya tiene factura, no
  acepta otra factura. Lo que falte o sobre se radica como nota.
- OCR del PDF y emparejamiento por IA dependen de servicios externos; sin ellos, una factura sin
  XML se captura a mano.

Changelog
=========

19.0.1.3.0 (2026-10-28)
-----------------------

Funciones que la v17 tenía y la 19 no, más ajustes de producción (DECISIONS.md #62 a #74).

Traídas de la v17:

- **Órdenes de los últimos 12 meses.** El formulario de radicar solo ofrece órdenes con
  ``date_order`` dentro de una ventana móvil de 12 meses (#62).
- **Campos ``spr_*`` protegidos por grupo.** ``spr_request_ids``/``count`` en contacto, orden y factura,
  y los documentos del proveedor, quedan solo para Validador y Responsable. Un "leer todos los
  campos" desde el POS ya no da AccessError (#63).
- **Flete aprobado.** Con producto de flete en Ajustes, ``EXTRA_CHARGES`` pasa a OK (antes siempre
  era observación). Se reconocen más nombres de flete y también el código de barras o la
  referencia del producto (#64).
- **Unidades con IA.** La línea guarda ``unit_code`` y ``uom_factor``, y cantidad y precio se comparan
  en la unidad de la orden. Revisión de unidades con IA y botón/acción **Validar con IA** (#65).
- **Vista previa del PDF y del XML, y PDF en el chatter.** Widget ``spr_preview_binary`` (el ojo en
  *Adjuntos*). El modelo hereda ``mail.thread.main.attachment``: el PDF queda como adjunto principal
  y se ve al lado del formulario (#66, #67). La migración copia el PDF de las solicitudes que ya
  existen.
- **Pestaña "Orden de compra".** Las líneas de las órdenes al lado de la factura, con subtotal y
  total comparados (#68).
- **Instructivo QWeb.** Reporte dinámico (compañía, NIT, hora de corte, cuenta de cobro en vez de
  XML) generado por el módulo y enlazado a la plantilla del correo, junto a la guía estática (#69).

Ajustes de producción:

- **Factura de proveedor.** El CUFE ya pasaba a la factura (ahora con test), la fecha contable es
  la de la factura y la línea de flete hereda la analítica de la orden (#70).
- **Botón Aprobar.** El Responsable deja en *Aprobada* una solicitud con observaciones ya
  revisada; quién y cuándo quedan en el formulario. Solo desde *Con observaciones*; revalidar o
  volver a borrador descarta la aprobación (#71).
- **Eventos RADIAN de receptor.** Botón **Generar eventos RADIAN** en el encabezado de la factura
  de proveedor: crea y valida en orden el acuse 030, el recibo del bien 032 y la aceptación
  expresa 033, cada uno en su savepoint. Solo sale en facturas publicadas, con fecha y CUFE, sin
  eventos previos y en un diario marcado como *Eventos RADIAN de receptor* (nunca de documento
  soporte). Antes de numerar revisa token, TestSetId y datos del firmante. Si un evento falla, los
  ya aceptados se conservan y el resultado queda en el chatter. Nada se genera solo al publicar.
  Sin dependencia dura de Jorels; ``cufe`` se copia a ``ei_uuid`` (#72). Verificar en STG.
- **Tope del flete.** Ajuste *Tope del flete (%)* (10 por defecto, 0 = sin tope): con producto de
  flete, un flete que supera ese porcentaje del subtotal de la mercancía (base contra base, sin
  IVA) queda como observación (#73).
- **Instructivo con los dos PDF** (reporte QWeb y guía estática), y precio en la unidad de la
  orden sin redondear a la moneda: con factor 12 la factura ya no suma 99.999,96 sobre 100.000.
  La revisión de unidades con IA no toca líneas emparejadas a mano y la migración del PDF no deja
  nota en el chatter (#74).

Tests: 209 (193 del módulo). Escáner: 0 BLOQUEA / 0 ROMPE / 1 REVISAR (falso positivo
documentado).

19.0.1.2.0 (2026-10-02)
-----------------------

Migración de Odoo 17 a Odoo 19 Community, con cambios de comportamiento pedidos durante la
validación.

Cambios de comportamiento:

- **Sin documentos no se radica.** Si a la empresa le falta la cámara de comercio, el RUT o la
  certificación bancaria, el formulario de radicar no se muestra ni procesa el envío. En ``/my``, en
  la lista y desde la orden de compra se ve el aviso con el enlace a *Mi cuenta*. La creación desde
  el backend no se bloquea.
- **Datos de facturación obligatorios en *Mi cuenta*.** Con Jorels instalado, el proveedor
  habilitado no guarda sin tipo de régimen, tipo de responsabilidad, municipio y email de
  facturación. Odoo 19 exige además código postal para Colombia. La zona del documento con error
  se pinta de rojo y la página baja hasta los errores.
- **Una actividad por validador y "Tomar revisión".** Los validadores se leen de
  ``all_user_ids``; en 19, ``user_ids`` dejaba fuera a los que heredan el grupo. Se crea una actividad
  por validador, sin dejarlos como seguidores. Nuevo campo *Revisor asignado*, botón **Tomar
  revisión**, aviso "En revisión por" para los demás, filtro *Mis revisiones* y *Agrupar por
  revisor*. Crear la factura, rechazar o cancelar cierran la revisión.
- **Analítica en las notas.** En 19 la línea de factura toma la analítica de ``purchase_line_id``, y
  las notas no tienen ese vínculo. Ahora la copian de la línea de la orden, como en 17.
- **Precisión de cantidades.** La precisión se llama ``Product Unit`` en 19. Con el nombre viejo,
  las cantidades se redondeaban a 2 decimales sin dar error.
- **Factura borrador sin número.** En 19 el nombre es ``False`` hasta confirmar; los mensajes usan
  la referencia del proveedor: "Factura de proveedor en borrador FEQA1001 creada…".
- **Correos a quien radica.** En 19 el autor del mensaje quedaba fuera de los destinatarios: quien
  radicaba no recibía "recibimos su factura" ni "requiere corrección" (una persona natural no
  recibía nada). Ahora les llega a la empresa y a quien radicó, una vez a cada uno.
- **CUFE en la factura de proveedor.** La factura y la nota crédito de proveedor muestran el
  *CUFE / CUDE del proveedor* con botón de copiar y el enlace *Consultar en la DIAN*; se puede
  buscar por CUFE.
- **Montos, cantidades y porcentajes en formato colombiano** en los hallazgos de la validación:
  ``$ 1.547.000,00``, ``factura 50, pendiente 40``, ``19,00 %``.
- **Destinatarios de los correos.** En 19 las plantillas vienen con *Destinatarios por defecto*
  activo y proponían destinatarios de más (por ejemplo *Administrator* en el instructivo). Las
  cinco plantillas usan otra vez su propio destinatario, como en 17.
- **Notas sobre facturas publicadas.** El selector de la factura que corrige la nota solo ofrece
  facturas publicadas. Si el XML apunta a una factura que sigue en borrador, la nota queda con
  observación, no rechazada.
- **Asteriscos en *Mi cuenta*.** Los datos de facturación electrónica y los documentos que faltan
  se marcan con el asterisco de obligatorio.
- **Instructivo.** Agrega el paso de cargar documentos y datos en *Mi cuenta* antes de radicar
  (se actualiza en la migración solo si la plantilla no fue personalizada).
- **Guía del instructivo adjunta.** El botón *Enviar instructivo del portal* abre el correo con
  la guía en PDF ya adjunta (attachment creada o reutilizada en el servidor y enlazada por id),
  en lugar de que compras la adjunte a mano en cada envío (DECISIONS.md #61).
- **JSON técnico solo para usuarios internos**: ``validation_json``, ``extracted_json`` y
  ``validation_summary`` llevan ``groups="base.group_user"``.

Correcciones tras la prueba en navegador (DECISIONS.md #54 a #59):

- Los correos "recibimos su factura" y "requiere corrección" llegan también a quien radicó. Antes,
  Odoo 19 lo excluía por ser el usuario activo.
- La factura y la nota crédito de proveedor muestran el **CUFE / CUDE del proveedor**, con botón
  para copiarlo y enlace *Consultar en la DIAN*.
- Los montos de los hallazgos salen en formato colombiano (``$ 1.547.000,00``). Solo en validaciones
  nuevas o revalidadas.
- La lista de "factura que corrige" de las notas solo trae facturas publicadas. Si el XML apunta a
  una en borrador, la solicitud queda con observación.
- *Mi cuenta*: asterisco de obligatorio en los cuatro datos de Jorels y en los documentos que
  falten; se quitó la insignia "Requerido para radicar".
- El instructivo tiene el paso "Cargue sus documentos y datos".
- El aviso "En revisión por" va en una línea, y el chatter dice "Factura de proveedor en borrador
  <ref> creada desde la solicitud…".

Adaptación a Odoo 19:

- El estado ``done`` de la orden de compra ya no existe; se quitó de dominios y estados abiertos.
- Listas ``<list>``, ``<chatter/>`` en el formulario, plantillas con ``t-out`` y campos renombrados en
  19, como ``product_uom_id`` y ``tax_ids``.

Scripts de migración (``migrations/19.0.1.2.0``):

- ``pre-migrate``: pasa a ``list`` las vistas del módulo que sigan como ``tree`` y renombra
  ``view_spr_request_tree`` a ``view_spr_request_list`` si el nuevo xmlid no existe.
- ``post-migrate``: reactiva con el ORM, cada una en su savepoint, las vistas del módulo que el
  upgrade dejó inactivas. No toca ``portal_my_home_spr``, que puede estar apagada a propósito.
  Actualiza el instructivo para el proveedor solo si conserva el texto de 17.

17.0.1.2.0
----------

- Los documentos del proveedor pasan a ser adjuntos del contacto, con vista previa. Solo se
  aceptan PDF de hasta 2 MB y sin contraseña.
- XML obligatorio para quien está obligado a facturar. Zonas de arrastrar y soltar.
- Una orden con una radicación en curso no acepta otra factura.

17.0.1.1.0
----------

- Varias órdenes de compra por solicitud.
- Notas crédito y débito, cuenta de cobro (documento soporte), fletes como cargo adicional y
  cierre de fin de mes.

Credits
=======

Authors
-------

- Libertario Coffee Roasters

Contributors
------------

- Miguel Bolivar (migración 17→19, endurecimiento, tests, documentación)
- Equipo Libertario Coffee Roasters (requisitos, comité funcional, validación funcional)
