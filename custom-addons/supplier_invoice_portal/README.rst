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

- Solo radican los proveedores marcados como **Puede radicar facturas en el portal**. Antes de
  radicar, cada uno tiene que cargar en *Mi cuenta* su cámara de comercio, su RUT y su
  certificación bancaria, y completar sus datos de facturación electrónica.
- Reglas automáticas: NIT del emisor y del adquiriente, CUFE repetido, estado de la orden, totales,
  impuestos, cantidades y precios contra lo pendiente de la orden, y tipo de documento.
- Fletes y envíos que la orden no trae: se marcan como **cargo adicional** y la factura los lleva
  con el producto de flete.
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

- Pulsar **Enviar instructivo del portal** en la ficha de la empresa. Se abre el correo con el
  paso a paso y la guía en PDF ya adjunta: solo hay que revisar los destinatarios y enviar.

.. figure:: ../static/description/02_instructivo.png
   :alt: Correo del instructivo del portal antes de enviarlo

   Correo del instructivo del portal antes de enviarlo

Permisos
--------

- **Validador**: ve las solicitudes, valida, empareja líneas a mano, toma la revisión y crea la
  factura borrador.
- **Responsable**: lo anterior, más rechazar, aceptar notas débito, devolver a borrador, cancelar
  y habilitar proveedores. *Compras: Administrador* es Responsable sin asignarlo.
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
   :alt: Con observaciones: flete que no está en la orden de compra

   Con observaciones: flete que no está en la orden de compra

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
  qué método (por código, por IA o manual). Si se cambia a mano la línea de la orden, hay que
  pulsar **Revalidar**; lo emparejado a mano se conserva. Los fletes quedan como **cargo
  adicional**.
- **Datos extraídos**: emisor, adquiriente, número, fecha y totales leídos del XML.
- **Adjuntos**: el PDF y el XML tal como los subió el proveedor.

.. figure:: ../static/description/24_backend_validacion.png
   :alt: Pestaña Validación

   Pestaña Validación

.. figure:: ../static/description/25_backend_lineas.png
   :alt: Líneas: emparejamiento manual y cargo adicional

   Líneas: emparejamiento manual y cargo adicional

.. figure:: ../static/description/26_backend_datos_extraidos.png
   :alt: Datos extraídos del XML

   Datos extraídos del XML

.. figure:: ../static/description/27_backend_adjuntos.png
   :alt: Adjuntos de la solicitud

   Adjuntos de la solicitud

Crear la factura
----------------

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

Pendiente de documentar
-----------------------

- **Pantalla de cierre de fin de mes** en el portal: solo se ve el último día hábil del mes,
  después de la hora de corte.
- **Icono** ``static/description/icon.png`` de 100×100: falta y necesita arte.

Límites conocidos
-----------------

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
