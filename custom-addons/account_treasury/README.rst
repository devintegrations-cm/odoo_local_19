================
Account treasury
================

..
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! Generado por .claude/scripts/gen_readme.py          !!
   !! Los cambios se sobrescriben: editar readme/*.md     !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-OPL--1-blue.png
    :target: https://www.odoo.com/documentation/user/legal/licenses/licenses.html
    :alt: License: OPL-1

|badge1| |badge2|

Avisa por correo al proveedor y a los solicitantes de compra cada vez que se registra un pago, y
deja a la vista quién pidió lo que se está pagando. Al confirmar el pago de una factura de
proveedor envía un correo al proveedor con el detalle de las facturas cubiertas, y otro a los
contactos que se hayan indicado en la orden de compra relacionada.

Para eso agrega tres cosas: el campo *Notificar pago a* (``notify_requester_ids``) en la orden de
compra, con el listado de correos calculado al lado; el campo *Solicitantes de Compra*
(``buyers_invoice_ids``) en la factura de proveedor, que muestra los usuarios que crearon las órdenes
de compra que se están facturando; y la trazabilidad del aviso en el pago, con la marca
*Notificación por correo* —visible también como columna en la lista de pagos a proveedor— y un
botón *Notificar Proveedor* para reenviarlo. El módulo está marcado como ``auto_install``: se instala
solo cuando ya están instalados ``account``, ``purchase`` y ``contacts``.

**Table of contents**

.. contents::
   :local:

Configuration
=============

El módulo no agrega ninguna opción en Ajustes: se configura orden por orden. En **Compras ›
Órdenes › Órdenes de compra**, debajo de la referencia del proveedor, se indican los contactos que
deben enterarse cuando esa compra se pague.

.. figure:: ../static/description/01_configuracion_orden_compra.png
   :alt: Campo Notificar pago a en la orden de compra

   Campo Notificar pago a en la orden de compra

- *Notificar pago a* acepta cualquier contacto de tipo *contacto*, no solo los del proveedor.
- *Correos a notificar pago* es de solo lectura: se arma con el correo de cada contacto elegido,
  así que un contacto sin correo simplemente no recibe nada.
- Para que el correo llegue de verdad hace falta un servidor de correo saliente configurado en
  **Ajustes › Técnico › Servidores de correo saliente**. Sin él el mensaje queda registrado en el
  historial del pago, pero no sale.
- La línea del método de pago del diario tiene que tener **cuenta de pagos pendientes**
  configurada. Ver ``ROADMAP`` antes de registrar el primer pago.

Usage
=====

Registrar el pago avisando
--------------------------

En la factura de proveedor se pulsa **Pay** y en el asistente aparece la casilla *Enviar
Notificación de pago*. Con la casilla marcada, al pulsar **Create Payment** el correo sale solo. La
casilla se oculta en los cobros de cliente: solo aplica a pagos salientes.

.. figure:: ../static/description/02_asistente_de_pago.png
   :alt: Casilla Enviar Notificación de pago en el asistente

   Casilla Enviar Notificación de pago en el asistente

El pago queda marcado y el correo registrado
--------------------------------------------

El pago creado muestra *Notificación por correo* marcado y los correos enviados en su historial:
uno al proveedor con el detalle de las facturas y otro a los contactos de la orden de compra. El
botón **Notificar Proveedor** permite reenviar el aviso en cualquier momento.

.. figure:: ../static/description/03_pago_notificado.png
   :alt: Pago con botón Notificar Proveedor y correos enviados

   Pago con botón Notificar Proveedor y correos enviados

Quién pidió lo que se factura
-----------------------------

En la factura de proveedor, justo debajo de *Bill Reference*, el campo *Solicitantes de Compra*
lista los usuarios responsables de las órdenes de compra facturadas. Es de solo lectura y se
calcula solo; si la factura no viene de una orden de compra, el campo no se muestra.

.. figure:: ../static/description/04_factura_solicitantes.png
   :alt: Campo Solicitantes de Compra en la factura de proveedor

   Campo Solicitantes de Compra en la factura de proveedor

A tener en cuenta durante el uso
--------------------------------

- **Todo proveedor con factura seleccionada necesita correo.** Si alguno no lo tiene, el asistente
  corta el registro del pago con el mensaje «Contactos in correo electrónico: …», marque o no la
  casilla de notificación.
- **El aviso a los solicitantes depende de la orden de compra.** Solo se envía si la factura pagada
  proviene de una orden de compra y esa orden tiene contactos en *Notificar pago a*. El correo al
  proveedor, en cambio, sale siempre.

Known issues / Roadmap
======================

- **La línea del método de pago necesita cuenta de pagos pendientes.** En Odoo 19 se puede
  confirmar un pago cuya línea de método de pago no tiene cuenta de pagos pendientes configurada, y
  ese pago queda **sin asiento contable** (en Odoo 17 era imposible). Sin asiento no hay
  conciliación, y sin conciliación el módulo no encuentra las facturas cubiertas: el correo sale
  sin el detalle de facturas y los solicitantes no se notifican. Hay que configurar la cuenta en el
  método de pago del diario **antes** de registrar pagos.
- **Falta ``static/description/icon.png``.** En la ficha de Apps se ve el cubo genérico de Odoo. Hace
  falta arte, no se inventa.
- **Tipo de cuenta bancaria, desactivado en 19.0.** Las vistas que agregaban *Tipo de cuenta
  bancaria* (ahorros / corriente) al partner y a su cuenta están comentadas en el manifiesto: en
  Odoo 19 el formulario de contacto ya no expone ``acc_number`` directamente. Quien lo necesite tiene
  que rehacerlas contra el widget de cuentas bancarias de 19.
- **Textos en español.** Las etiquetas de los campos y las plantillas de correo están escritas en
  español, sin traducción a otros idiomas.

Credits
=======

Authors
-------

- Osmar Toloza

Contributors
------------

- Osmar Toloza
