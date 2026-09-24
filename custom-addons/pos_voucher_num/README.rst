===========================
POS popup Validation Number
===========================

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

Pide el número de aprobación (voucher) al cobrar con tarjeta y lo guarda en la
línea de pago del punto de venta. Cuando un método de pago del POS tiene
activada la casilla **«Ask for approval number»**, el POS abre un diálogo y pide
el número de voucher *antes* de crear la línea de pago: valida que sean como
máximo 11 caracteres alfanuméricos, y si el cajero descarta el diálogo o el dato
no cumple, la línea de pago no se agrega.

El número queda visible en la línea de pago junto al importe durante todo el
cobro, se guarda en el pedido y después se consulta desde el backend. Los
métodos de pago que no tienen la casilla marcada siguen funcionando como
siempre: el módulo no interfiere con ellos.

**Table of contents**

.. contents::
   :local:

Configuration
=============

Ir a *Punto de Venta > Configuración > Métodos de pago*, abrir el método con el
que se cobra con tarjeta y marcar **«Ask for approval number»**. La casilla está
debajo de «Identify Customer», en el formulario del método.

Odoo **no permite guardar** la configuración de un método de pago mientras haya
una sesión de POS abierta: para cambiar esta casilla hay que **cerrar la caja**
primero.

Después de guardar, recargar la pantalla del POS no alcanza: hay que volver a
entrar desde el backend (botón *Continue Selling* / *Open Register*) para que la
caja tome la nueva configuración.

Usage
=====

La casilla está en el formulario del método de pago:

.. figure:: ../static/description/01_configuracion.png
   :alt: Casilla Ask for approval number en el método de pago del POS

   Casilla Ask for approval number en el método de pago del POS

En la pantalla de pago, al elegir el método configurado, el POS pide el número
de aprobación. Se escribe el voucher del datáfono y se confirma con **«Apply»**:

.. figure:: ../static/description/02_pos_dialogo.png
   :alt: Diálogo del POS pidiendo el número de aprobación

   Diálogo del POS pidiendo el número de aprobación

El número aparece entre corchetes junto al importe, tanto en la línea
seleccionada como en las demás. Un pedido puede tener varias líneas del mismo
método, cada una con su propio voucher:

.. figure:: ../static/description/03_pos_lineas.png
   :alt: Líneas de pago del POS mostrando el número de voucher junto al importe

   Líneas de pago del POS mostrando el número de voucher junto al importe

Una vez validado el pedido, el número se consulta en *Punto de Venta >
Pedidos*, pestaña **«Payments»**, columna **«Voucher Number»**. El mismo campo
está en el formulario del pago del POS (*Punto de Venta > Pedidos > Pagos*) y
como columna opcional en la conciliación bancaria:

.. figure:: ../static/description/04_backend_pedido.png
   :alt: Pedido del POS en el backend con la columna Voucher Number

   Pedido del POS en el backend con la columna Voucher Number

Known issues / Roadmap
======================

- El campo se renombró de ``vaucher_num`` (errata heredada) a ``voucher_num`` en
  la versión 19.0.1.1.0 mediante migración ``RENAME`` atómico. La migración
  19.0.1.1.0 mantiene una compatibilidad temporal que acepta payloads legacy
  ``vaucher_num`` y los mapea a ``voucher_num`` con un log ``WARNING``; se
  retirará en 19.0.1.2.0 junto con el DROP de las columnas huérfanas, cuando
  ningún POS con assets antiguos siga en uso.
- **Depende de ``account_accountant`` (Odoo Enterprise)**: el módulo extiende una
  vista de la conciliación bancaria. Sin Enterprise no se instala.
- El núcleo **no permite guardar** la casilla del método de pago con una sesión
  de POS abierta: hay que cerrar la caja para poder cambiarla.
- Falta ``static/description/icon.png``. El módulo se publica sin icono propio.
- La validación acepta hasta 11 caracteres alfanuméricos, sin espacios ni
  signos. El límite no es configurable.
- Probado sobre Odoo 19.0. No es compatible con versiones anteriores.
- El módulo se instala automáticamente (``auto_install``) cuando están presentes
  sus dependencias.

Credits
=======

Authors
-------

- Osmar Toloza

Contributors
------------

- Osmar Toloza \<<desarrollo@libertariocoffee.com>\>
