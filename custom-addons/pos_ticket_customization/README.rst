========================================
POS - Información adicional en el ticket
========================================

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

Agrega al ticket del Punto de Venta **bloques de información adicional** configurables por tienda:
texto, texto legal, separadores, imágenes, códigos QR y códigos de barras. Cada punto de venta
tiene su propia lista de bloques, ordenable y con activación individual, y cada bloque se imprime
en una de tres posiciones del ticket: **cabecera**, **antes del pie** o **final del ticket**.

Tipos de bloque disponibles: texto libre, texto legal (letra más pequeña), separador, imagen, QR de
URL, QR de texto, código de barras, QR de reseña en Google, QR de WhatsApp, QR de WiFi, QR de
contacto (vCard) y QR de pago o propina.

Cada bloque puede limitarse por **vigencia** (fechas desde/hasta), **importe mínimo** del pedido y
**frecuencia** (uno de cada N pedidos). El contenido admite marcadores que se reemplazan al imprimir
con datos del pedido, como ``{order_name}``, ``{total}`` o ``{cashier}``.

Los QR y códigos de barras los genera el propio Odoo con el endpoint ``/report/barcode``; no se usa
ninguna librería JavaScript externa. Las imágenes se incrustan en el ticket, así que se siguen
imprimiendo aunque la caja pierda la conexión, y si un código no se puede generar se imprime la
misma información en texto.

**Table of contents**

.. contents::
   :local:

Installation
============

Dependencias
------------

- ``point_of_sale``. No hay dependencias externas ni librerías de Python adicionales.

Pasos de instalación
--------------------

Instalar el módulo desde *Aplicaciones*. Crea el modelo ``pos.receipt.custom.block``, sus permisos y
una regla multicompañía. Después de instalar o actualizar, hay que **volver a entrar al POS** desde
el backend (o recargar la pestaña) para que cargue los archivos nuevos y los bloques.

Permisos
--------

- **Administrador del POS** (``point_of_sale.group_pos_manager``) y **Ajustes** (``base.group_system``):
  lectura y escritura de bloques.
- **Usuario del POS** (``point_of_sale.group_pos_user``): solo lectura, que es lo que necesita la
  caja para cargar los bloques al abrir la sesión.

Migración desde Odoo 17
-----------------------

El módulo conserva el nombre técnico, el modelo y los nombres de campo de la versión 17, así que
los bloques ya configurados se mantienen sin script de datos. Lo que cambió es el código del POS:
la carga de datos pasó al contrato ``pos.load.mixin`` de Odoo 19 y el ticket se arma a partir del
pedido vivo en lugar de ``export_for_printing()``.

Configuration
=============

Los bloques se configuran por punto de venta. El acceso principal está en *Punto de venta ›
Configuración › Punto de venta*: al abrir una tienda, al final del formulario aparece la sección
**Ticket – Información adicional**, con una lista editable en línea. Cada fila es un bloque; se
reordenan arrastrando el ícono de la izquierda y se apagan con el interruptor **Activo**.

.. figure:: ../static/description/01_configuracion.png
   :alt: Punto de venta › Configuración › Punto de venta › (tienda): sección Ticket – Información adicional

   Punto de venta › Configuración › Punto de venta › (tienda): sección Ticket – Información adicional

Hay dos accesos más al mismo modelo:

- *Punto de venta › Configuración › Ajustes*, bloque **Recibos y facturas**, opción **Información
  adicional en el ticket**: muestra cuántos bloques activos tiene la tienda elegida arriba y el
  botón **Configurar bloques**, que abre la lista de esa tienda.
- *Punto de venta › Configuración › Ticket – Información adicional*: lista de todas las tiendas,
  con filtros para agrupar por punto de venta, tipo o posición y para ver los archivados.

.. figure:: ../static/description/02_ajustes.png
   :alt: Ajustes › Punto de venta › Recibos y facturas: opción Información adicional en el ticket

   Ajustes › Punto de venta › Recibos y facturas: opción Información adicional en el ticket

Todas las opciones requieren el grupo **Administrador del POS**. Si no hay ningún bloque, el ticket
se imprime igual que el estándar de Odoo.

Campos de un bloque
-------------------

Al abrir un bloque desde la lista global o desde *Configurar bloques* se ve el formulario completo.
Los grupos de campos cambian según el tipo elegido.

.. figure:: ../static/description/03_bloque.png
   :alt: Formulario de un bloque de tipo QR de WiFi

   Formulario de un bloque de tipo QR de WiFi

- **Punto de venta** (obligatorio): la tienda dueña del bloque. Si se elimina la tienda, se
  eliminan sus bloques.
- **Tipo** (obligatorio, por defecto *Texto libre*): define qué se imprime y qué campos se piden.
- **Posición** (obligatoria, por defecto *Antes del pie*): *Cabecera*, *Antes del pie* o *Final del
  ticket*.
- **Alineación** (obligatoria, por defecto *Centro*): izquierda, centro o derecha.
- **Secuencia** (por defecto 10): orden de impresión dentro de la misma posición.
- **Leyenda** (opcional): texto que se imprime encima del bloque. Admite marcadores.
- **Contenido**: obligatorio para texto libre, texto legal, QR de URL, QR de texto, código de
  barras, QR de reseña y QR de pago. Es el texto, la URL o el valor del código. Admite marcadores.
- **Imagen** (obligatoria para el tipo *Imagen*): se reduce a 512 px como máximo al guardar.
- **WhatsApp**: *Número* (obligatorio, formato internacional sin "+" ni espacios, por ejemplo
  573001234567) y *Mensaje* prellenado (opcional, admite marcadores).
- **WiFi**: *SSID* (obligatorio), *Seguridad* (por defecto WPA/WPA2), *Contraseña* y *Red oculta*.
- **Contacto (vCard)**: *Nombre* (obligatorio), organización, teléfono, correo, sitio web y
  dirección.
- **Simbología** (solo código de barras, por defecto Code 128) y **Mostrar valor** (imprime el
  valor legible bajo las barras).
- **Ancho / Alto (px)** (por defecto 150 × 150; al elegir *Código de barras* pasa a 300 × 60): entre
  1 y 1000 px. Para impresora térmica se recomiendan QR de 120 a 200 px.
- **Vigente desde / hasta** (opcionales): vacío significa sin límite.
- **Importe mínimo** (por defecto 0): el bloque solo sale si el total con impuestos del pedido es
  igual o mayor. 0 significa sin mínimo.
- **Cada N pedidos** (obligatorio, por defecto 1) y **Desplazamiento** (por defecto 0): con 1 sale en
  todos los pedidos; con 10, en los pedidos 10, 20, 30… de la sesión de caja. El desplazamiento
  corre el ciclo (con 10 y desplazamiento 5, sale en 5, 15, 25…) y debe estar entre 0 y N − 1.

Para el QR de reseña, el *Contenido* puede ser el Place ID de Google o una URL completa: si empieza
por ``http`` se usa tal cual; si no, se arma el enlace de reseña de Google con ese Place ID.

Validaciones al guardar
-----------------------

- Cada tipo exige sus campos obligatorios (contenido, imagen, número, SSID o nombre de contacto).
- EAN-8 y EAN-13 deben tener la longitud y el dígito de control correctos, salvo que el valor lleve
  marcadores.
- *Vigente desde* no puede ser posterior a *Vigente hasta*.
- Ancho y alto deben ser mayores que 0 y no pasar de 1000 px.

Marcadores
----------

Disponibles en *Contenido*, *Leyenda* y *Mensaje de WhatsApp*: ``{order_name}``, ``{total}``, ``{date}``,
``{cashier}``, ``{table}``, ``{partner_name}``, ``{tracking_number}`` y ``{store_name}``. Un marcador que no
existe se imprime tal cual, para que el error se vea en el ticket.

A tener en cuenta:

- Los cambios se ven en el POS después de volver a entrar a la sesión o recargar la pestaña: los
  bloques se cargan al abrir el POS.
- Los bloques archivados no se cargan en el POS.

Usage
=====

Flujo
-----

No hay ningún paso nuevo para el cajero. Al terminar un pedido, el ticket incluye los bloques
activos de la tienda que cumplen sus condiciones (vigencia, importe mínimo y frecuencia), cada uno
en su posición:

- **Cabecera**: justo debajo del encabezado estándar (datos del pedido, cajero y cliente).
- **Antes del pie**: después de los totales, los pagos y el QR de autofacturación de Odoo, antes del
  pie configurable de la tienda.
- **Final del ticket**: después del pie y de los comprobantes del datáfono.

Los mismos bloques salen en la pantalla de recibo, en la impresión, en la reimpresión desde
*Órdenes › Imprimir recibo* y en el recibo enviado por correo.

.. figure:: ../static/description/04_recibo.png
   :alt: Ticket reimpreso con bloques en las tres posiciones

   Ticket reimpreso con bloques en las tres posiciones

La captura es la vista de impresión de un ticket reimpreso desde *Órdenes*, con cinco bloques de
ejemplo: un texto libre en la cabecera, un QR de WiFi antes del pie y, al final, un separador, un
QR de propina cuya leyenda usa ``{order_name}`` y un texto legal.

Casos especiales
----------------

- **Reimpresión**: la frecuencia se calcula con el número de pedido dentro de la sesión de caja,
  que se guarda con el pedido. Una reimpresión muestra los mismos bloques que el ticket original.
- **Sin conexión**: los códigos que no dependen del pedido se descargan al abrir la sesión y quedan
  en memoria. Los que llevan marcadores se generan al imprimir; si en ese momento no hay conexión,
  el bloque imprime la información en texto (SSID y clave del WiFi, la URL, el teléfono…).
- **Recibo básico** (el que Odoo imprime sin precios, para regalos): los bloques de la posición
  *Antes del pie* no salen, porque Odoo omite esa parte del ticket. Los de cabecera y final sí.
- **Restaurante**: con ``pos_restaurant``, ``{order_name}`` se reemplaza por el nombre que Odoo le da
  al pedido en la mesa (por ejemplo "T 5"), no por la referencia del pedido. Para imprimir una
  referencia única conviene usar ``{tracking_number}``.

Solución de problemas
---------------------

- **Un bloque no aparece en el ticket.** Revisar que esté activo, que la fecha de hoy esté dentro
  de la vigencia, que el total alcance el importe mínimo y que *Cada N pedidos* sea 1 (o que le
  toque a ese pedido). Después de cambiar algo, recargar el POS.
- **Un bloque con *Cada N pedidos* no sale nunca.** El conteo se reinicia en cada sesión de caja: si
  la tienda hace menos de N pedidos por turno, el bloque no llega a imprimirse. Bajar N.
- **Aparece ``{algo}`` literal en el ticket.** El marcador está mal escrito; ver la lista en
  *Configuración*.
- **Sale el texto en lugar del código.** El código no se pudo generar (sin conexión con el
  servidor). Al recuperar la conexión, la siguiente impresión vuelve a intentarlo.
- **Un bloque archivado no aparece en la lista de la tienda.** La lista del formulario de la tienda
  solo muestra los activos; para reactivarlo, usar el menú *Ticket – Información adicional* con el
  filtro *Archivado*.

Known issues / Roadmap
======================

Limitaciones conocidas
----------------------

- **``{order_name}`` en restaurante.** Toma el valor de ``getName()`` del pedido, que en
  ``pos_restaurant`` devuelve el nombre de la mesa ("T 5") o el texto de venta directa, no la referencia. En la
  captura de uso se ve así.
- **Recibo básico.** Los bloques *Antes del pie* se insertan junto a ``div.before-footer``, que en la
  plantilla de Odoo 19 está dentro de ``t-if="!props.basic_receipt"``; en un recibo básico no salen.
- **Bloques archivados en el formulario de la tienda.** El campo ``custom_receipt_block_ids`` lleva
  ``context="{'active_test': False}"``, pero la lista embebida solo muestra los activos. Se ven y se
  reactivan desde el menú global o desde *Configurar bloques*.
- **El contador de Ajustes cuenta solo los activos**, aunque la etiqueta dice *Bloques
  configurados*.
- La frecuencia se reinicia en cada sesión de caja (usa ``sequence_number``).
- Las etiquetas de la interfaz están en español dentro del código y no hay ``i18n/``.
- No hay vista previa del bloque en el formulario: el resultado se ve en el POS.
- Falta ``static/description/icon.png``: en *Aplicaciones* se ve el ícono genérico de Odoo.

Componentes
-----------

- ``models/pos_receipt_custom_block.py``: el modelo ``pos.receipt.custom.block`` (hereda
  ``pos.load.mixin``), sus validaciones y la lista de campos que se envían al POS
  (``POS_LOADED_FIELDS``).
- ``models/pos_session.py``: agrega el modelo en ``_load_pos_data_models()``. El dominio de carga solo
  trae los bloques activos de la tienda de la sesión.
- ``models/pos_config.py``: el One2many ``custom_receipt_block_ids`` y la acción que abre los bloques de
  una tienda.
- ``models/res_config_settings.py``: el contador y el botón de *Ajustes*.
- ``views/``: la sección en el formulario de ``pos.config``, la opción en *Ajustes › Recibos y
  facturas*, las listas, el formulario, la búsqueda y el menú global.
- ``security/``: permisos por grupo y regla multicompañía sobre el ``company_id`` heredado de la tienda.
- ``static/src/utils/receipt_block_utils.js``: URLs de ``/report/barcode``, payloads de WiFi, vCard,
  WhatsApp y reseña, marcadores y texto de respaldo.
- ``static/src/app/services/pos_store.js``: parche de ``PosStore``; carga los bloques, filtra por
  vigencia, importe y frecuencia, resuelve marcadores e incrusta las imágenes como ``data:`` URI.
- ``static/src/app/services/printer_service.js``: parche de ``PrinterService.print()`` que incrusta los
  códigos antes de rasterizar.
- ``static/src/app/screens/receipt_screen/receipt_screen.js``: parche de ``_sendReceiptToCustomer()``
  para el envío por correo.
- ``static/src/app/screens/receipt_screen/receipt/order_receipt.js``, ``.xml`` y ``.scss``: ``setup()`` y el
  getter ``customReceiptBlocks`` de ``OrderReceipt``, la herencia de la plantilla
  ``point_of_sale.OrderReceipt`` y los estilos (clases ``o_ptc_*``).

Notas para mantenimiento
------------------------

- **Puntos de anclaje en la plantilla.** La herencia usa ``//ReceiptHeader`` (after),
  ``//div[hasclass('before-footer')]`` (before) y ``//div[hasclass('after-footer')]`` (inside). Los tres
  existen en ``point_of_sale.OrderReceipt`` de Odoo 19. La herencia se resuelve en el navegador: si una
  versión futura quita alguno, la instalación no avisa y el error aparece al abrir el POS.
- **``OrderReceipt`` no tiene ``setup()`` en Odoo 19.** El parche define uno para tener ``this.pos`` con
  ``usePos()``. Si el core agrega su propio ``setup()``, el parche debe llamar a ``super.setup()``.
- **Por qué se incrustan las imágenes.** Al imprimir, ``htmlToCanvas`` cachea cada recurso por URL
  **sin la query string** (``getCacheKey`` en ``point_of_sale/static/src/app/utils/html-to-image.js``).
  Todos los códigos son ``/report/barcode/?...``, así que sin incrustarlos el primer código se
  repetiría en todos los bloques. Con ``data:`` URI esa caché no interviene. En la reimpresión de la
  captura, los dos QR del ticket llegaron como ``data:image/png;base64``.
- **Simbologías.** Los valores del selector son nombres de ReportLab (``Standard39``, ``I2of5``), no
  ``Code39`` ni ``ITF``: con un nombre inválido ``ir.actions.report.barcode()`` lanza ``KeyError``, el
  endpoint responde 500 y el ticket sale con la imagen rota.
- **Tope de 1000 px por lado.** ``ir.actions.report.barcode()`` rechaza imágenes de más de 1 200 000
  px²; el endpoint lo devuelve como HTTP 200 con HTML y el ``<img>`` sale roto sin error en el log. La
  validación del modelo lo evita.
- **Query string en ``/report/barcode``.** Se usa ``?barcode_type=..&value=..`` en lugar de la forma de
  ruta, porque los payloads de WiFi, vCard y URLs llevan ``/`` y saltos de línea.
- **Tests.** ``tests/test_receipt_custom_block.py`` (22 tests: validaciones, carga al POS, campo
  imagen, integración con ``pos.config`` y el contrato con ``barcode()`` del core) y
  ``static/tests/receipt_block_utils_tests.js`` (QUnit, funciones de ``receipt_block_utils.js``). Los
  parches del POS no tienen test automático: se validan en el navegador.

Credits
=======

Authors
-------

- Libertario Coffee

Contributors
------------

- Libertario Coffee
- Cristian Mira (migración a Odoo 19)
