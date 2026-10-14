======================================
POS — Factura Electrónica Cliente DIAN
======================================

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

Agrega al POS un botón **Factura electrónica** para que el cajero valide ante la DIAN al cliente
que pide factura electrónica **antes** de asignarlo a la orden. Consulta el registro de adquirentes
de la DIAN a través del servicio **Edipo de Jorels**, con el mismo token (``api_key``) con el que la
compañía factura.

Con el resultado, el cajero ve el nombre que registró la DIAN, el documento tal como se guardará
(p.ej. ``890903938-8``) y el correo, y decide:

- **Asignar** al cliente que ya existe en Odoo. Si le faltan datos de facturación, se completan solo
  los campos **vacíos**. Nunca se pisan valores existentes, salvo que el cajero marque
  *Reemplazar nombre y correo con los datos de la DIAN*.
- **Crear y asignar** al cliente que la DIAN confirma y no existe en Odoo. Se crea con el nombre tal
  como lo devuelve la DIAN, régimen *No responsable de IVA*, responsabilidad *No aplica – Otros*,
  el municipio de la compañía y país Colombia. Si la DIAN no tiene correo, el popup se lo pide al
  cajero.
- **No asignar a nadie** si la DIAN no confirma el documento, si el número existe en Odoo con otro
  tipo de documento o si hay un error de configuración o de conexión. Cada caso muestra un mensaje
  distinto para que no se confunda un "no registrado" con una falla del servicio.

Una vez asignado el cliente, la orden queda marcada para **Factura**.

**Importante:** los datos que devuelve la DIAN los registraron los emisores que ya le facturaron a
ese cliente, y pueden estar desactualizados o ser de otra persona. El cajero tiene que confirmar el
nombre y el correo con el cliente antes de asignar.

**Efecto colateral:** el módulo **oculta siempre** el botón nativo *Guardar orden* (ícono de
subida, ``fa-upload``) en la pantalla de producto y en la barra de acciones de pantallas chicas, esté
activo o no el botón *Factura electrónica* en esa caja.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Requisitos
----------

- Módulo ``l10n_co_edi_jorels`` instalado, con la **facturación electrónica habilitada** en la
  compañía. Si no lo está, el popup responde "La facturación electrónica no está habilitada en esta
  compañía".
- **Token Edipo** en la compañía: *Ajustes › Facturación electrónica colombiana*, campo
  **Edipo api key** (``api_key``). Es el mismo que usa la instancia para facturar. Sin él, el popup
  responde "No está configurado el token de Edipo"; si el token no es válido, avisa que no está
  autorizado.
- **Municipio de la compañía** (campo *Municipality* de facturación electrónica). Los clientes nuevos
  y los existentes que no tienen municipio toman el de la compañía. Si la compañía tampoco lo tiene,
  el cliente existente se informa como incompleto y no se asigna, y el cliente nuevo **se crea sin
  municipio** (ver *Known issues / Roadmap*).
- **Permisos del cajero:** usuario del Punto de Venta. Para *Crear y asignar* o *Asignar y
  actualizar* necesita además permiso de creación y edición de contactos; sin él, el popup lo
  informa y no escribe nada.

Activar el botón en cada caja
-----------------------------

En *Punto de Venta › Configuración › Puntos de venta*, abrir la caja y, en la pestaña
**Configuración**, marcar **Factura electrónica: validación DIAN del cliente**. El ajuste viene
marcado de forma predeterminada; desmarcarlo oculta los botones *Factura electrónica* en esa caja.
El botón *Guardar orden* queda oculto igual, con el ajuste marcado o no.

.. figure:: ../static/description/01_configuracion.png
   :alt: Punto de Venta › Configuración › Puntos de venta › (caja) › Configuración: marcar «Factura electrónica: validación DIAN del cliente»

   Punto de Venta › Configuración › Puntos de venta › (caja) › Configuración: marcar «Factura electrónica: validación DIAN del cliente»

La caja puede tener una sesión abierta mientras se cambia el ajuste. El POS lo toma la próxima vez
que se carga.

Opcional
--------

La URL del servicio se cambia con el parámetro de sistema ``jorels.edipo.api_url`` (por defecto
``https://edipo.jorels.com``).

Usage
=====

1. Abrir el popup
-----------------

En la pantalla de producto, con la orden en curso, pulsar **Factura electrónica**, a la derecha de
*Cliente*. En pantallas chicas el botón aparece en la barra de acciones como **FE**. También está
en la pantalla de pago, debajo de *Cliente* y *Recibo/Factura*.

.. figure:: ../static/description/02_boton_producto.png
   :alt: Pantalla de producto: botón «Factura electrónica» junto a Cliente

   Pantalla de producto: botón «Factura electrónica» junto a Cliente

Las órdenes con devoluciones no permiten cambiar el cliente: el botón muestra un aviso y no abre el
popup.

2. Digitar el documento
-----------------------

Elegir el **tipo de documento**, escribir el **número** y pulsar **Validar en DIAN**. Para NIT, el
dígito de verificación es opcional. Se aceptan también ``NIT-DV`` (p.ej. ``890903938-8``) y el NIT de
10 dígitos con el DV pegado, si empieza por 8 o 9. Un DV que no corresponde se rechaza e indica el
correcto. El documento genérico de consumidor final (``222222222222``) se rechaza: para ese caso se
usa el botón *Cliente*.

.. figure:: ../static/description/03_popup_datos.png
   :alt: Popup: tipo de documento, número y Validar en DIAN

   Popup: tipo de documento, número y Validar en DIAN

3. Revisar la previsualización y confirmar
------------------------------------------

Arriba aparecen el nombre que registró la DIAN, el documento en grande tal como se guardará y el
correo. **Confirmar con el cliente** que el nombre y el correo son los suyos. Si algo no coincide,
**Modificar datos** vuelve al paso anterior.

Cliente nuevo en Odoo: **Crear y asignar**. Se crea con los datos de la DIAN y los valores fiscales
por defecto. En empresas (NIT), un aviso azul pide confirmar los datos fiscales con el cliente.

.. figure:: ../static/description/04_previsualizacion_crear.png
   :alt: Cliente confirmado por la DIAN que no existe en Odoo: Crear y asignar

   Cliente confirmado por la DIAN que no existe en Odoo: Crear y asignar

Cliente que ya existe en Odoo: se muestra debajo de los datos de la DIAN. **Asignar y actualizar**
solo completa los campos vacíos (correo de facturación, municipio, régimen, responsabilidad, formato
del NIT). Si el nombre o el correo difieren de los de la DIAN, la casilla **Reemplazar nombre y
correo con los datos de la DIAN** los sobrescribe; sin marcarla, no se tocan. Si no hay nada que
completar, el botón dice **Asignar cliente**.

.. figure:: ../static/description/05_previsualizacion_existente.png
   :alt: Cliente existente: casilla para reemplazar nombre y correo, y Asignar y actualizar

   Cliente existente: casilla para reemplazar nombre y correo, y Asignar y actualizar

Al confirmar, el popup se cierra, el cliente queda en la orden y aparece la notificación
"Cliente … asignado para factura electrónica".

4. Casos en que no se asigna
----------------------------

Si la DIAN no tiene registrado el documento, el cliente tiene que habilitarse como adquirente ante
la DIAN. Se cierra con **Entendido**.

.. figure:: ../static/description/06_no_registrado.png
   :alt: No registrado ante la DIAN

   No registrado ante la DIAN

Si el número ya existe en Odoo con **otro tipo de documento** (p.ej. guardado como NIT y consultado
como cédula), el popup no escribe nada y avisa en amarillo con qué tipo existe. Hay que consultarlo
con ese tipo o corregir el contacto en *Contactos*.

.. figure:: ../static/description/07_tipo_distinto.png
   :alt: El número existe en Odoo con otro tipo de documento

   El número existe en Odoo con otro tipo de documento

5. Cobrar
---------

En la pantalla de pago, el cliente aparece asignado y **Recibo/Factura** marcado. Al validar el
pago, la factura sale a nombre de ese cliente y ``l10n_co_edi_jorels`` la envía a la DIAN.

.. figure:: ../static/description/08_pago_factura.png
   :alt: Pantalla de pago: cliente asignado y Recibo/Factura marcado

   Pantalla de pago: cliente asignado y Recibo/Factura marcado

Estados y mensajes del popup
----------------------------

- **Cliente nuevo** (``create_ok``): "El cliente existe ante la DIAN y no en Odoo. Se creará con sus
  datos." Botón *Crear y asignar*.
- **Falta correo** (``needs_email``): "La DIAN confirmó a … pero no tiene correo registrado". Pide el
  correo al cajero (obligatorio y con formato válido) y luego *Crear y asignar*. Los correos de
  relleno de la DIAN (``sininformacion@…``, ``sincorreo@…``) cuentan como "sin correo".
- **Cliente existente** (``found``): muestra el cliente de Odoo. Botón *Asignar cliente* o *Asignar y
  actualizar*.
- **No registrado** (``not_registered``): "El cliente … no está habilitado como adquirente ante la
  DIAN". Botón *Entendido*.
- **Otro tipo de documento** (``type_mismatch``): "Existe en Odoo como …; consúltelo con ese tipo o
  corríjalo en Contactos". Aviso amarillo, no escribe nada.
- **Duplicado** (``ambiguous``): "Hay más de un contacto con este documento". Lista los contactos y
  hay que resolverlo en *Contactos*.
- **Archivado** (``archived``): "El cliente existe en Odoo pero está ARCHIVADO". Hay que reactivarlo
  en *Contactos*.
- **Incompleto** (``incomplete``): "El cliente existe en Odoo pero le falta: …" (correo de facturación
  sin correo de la DIAN para completarlo, o municipio sin municipio en la compañía).
- **Dato inválido** (``invalid``): número vacío, NIT de menos de 7 dígitos, DV que no concuerda,
  documento de consumidor final, correo con formato inválido. Botón *Modificar datos*.
- **Configuración** (``config_error``): facturación electrónica deshabilitada, token ausente o no
  autorizado. Botón *Cerrar*.
- **Conexión** (``connection_error``): "La DIAN no respondió (…). Reintente en unos segundos." Botón
  *Reintentar*.
- **Respuesta inesperada** (``unexpected_response``): el servicio rechazó la consulta o respondió
  algo que no se reconoce. Botón *Reintentar*.
- **Permisos** (``permission_error``): el usuario no puede leer, crear o editar contactos. Botón
  *Cerrar*.

En todos los casos que no son de asignación, la orden queda como estaba.

Known issues / Roadmap
======================

Límites conocidos
-----------------

- **Los datos de la DIAN no son del cliente que está en la caja.** El servicio de adquirentes
  devuelve lo que registraron otros emisores. El cajero tiene que confirmar nombre y correo con el
  cliente; el popup no lo puede verificar.
- **Guardar orden oculto en todas las cajas.** El botón nativo *Guardar orden* (``fa-upload``) se
  quita de la pantalla de producto y de la barra de acciones aunque la caja tenga desmarcado
  *Factura electrónica: validación DIAN del cliente*.
- **Otro tipo de documento muestra los datos de la DIAN.** En el aviso *Existe en Odoo como …*, el
  popup igual muestra nombre y correo que la DIAN devolvió para el número con el tipo consultado,
  que puede ser una persona distinta del contacto de Odoo. Evaluar ocultar ese bloque en
  ``type_mismatch``.
- **Pantallas chicas:** con un cliente asignado, el botón **FE** de la barra de acciones queda
  reducido al ícono y "…".
- Cada validación de un cliente existente vuelve a consultar a la DIAN (por diseño del
  requerimiento). Si el volumen de cajas lo pide, evaluar una caché corta por documento.
- El buscador de existentes compara las variantes canónica ``NIT-DV``, sin DV y sin guion, pero no NIT
  guardados con puntos (``900.123.456-8``). Si aparecen en producción, agregar esa variante.

Mejoras pendientes (no bloquean)
--------------------------------

- **Timeout de Edipo:** hoy es de 20 s. Pasarlo a 5 s de conexión y 10 s de lectura
  (``timeout=(5, 10)``) para que la caja no quede esperando.
- **Crear sin municipio:** bloquear *Crear y asignar* si la compañía no tiene municipio. Hoy el
  cliente nuevo se crea con el municipio vacío.
- **Teclado:** que Enter dispare *Validar en DIAN* y que el foco inicial quede en el número.
- **Modificar datos:** limpiar el correo digitado al volver al formulario, para que no quede
  arrastrado a otro documento.
- **Índice sobre ``edi_sanitize_vat``:** decidir según el volumen de contactos en producción. La
  búsqueda de existentes filtra por ese campo en cada consulta.
- **Concurrencia:** dos cajas que crean el mismo cliente al mismo tiempo pueden dejar un duplicado,
  que la próxima consulta informará como *Hay más de un contacto con este documento*.
- **Rotación del token Edipo:** el ``api_key`` quedó expuesto en sesiones de trabajo previas.
  Rotarlo antes de producción (decisión del equipo).
- **Mapeo de más campos de Edipo:** si ``/acquirer`` devuelve municipio, régimen o responsabilidad
  del adquirente, usarlos en lugar de los valores por defecto.
- Ícono del módulo (``static/description/icon.png``): falta y requiere arte.

Credits
=======

Authors
-------

- Libertario Coffee Colombia

Contributors
------------

- Desarrollo Libertario \<<regionalit@libertariocoffee.com>\>
