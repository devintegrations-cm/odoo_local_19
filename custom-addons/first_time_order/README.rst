================
First Time Order
================

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

Guarda la fecha del **primer** pedido del Punto de Venta y no la modifica despues. Agrega el campo
*First order* al pedido del Punto de Venta: el valor se fija cuando el pedido se crea y **no se
vuelve a tocar**, aunque despues cambie la fecha del pedido.

Sirve para saber cuando entro originalmente una venta, con independencia de correcciones
posteriores. No requiere ninguna configuracion: con instalar el modulo alcanza, el campo aparece
solo y se llena solo.

**Table of contents**

.. contents::
   :local:

Usage
=====

Entra a *Punto de Venta › Pedidos* y abri cualquier pedido. El campo **First order** esta justo
debajo de *Date*.

.. figure:: ../static/description/01_campo_first_order.png
   :alt: Campo First order en el formulario del pedido de Punto de Venta

   Campo First order en el formulario del pedido de Punto de Venta

- El campo es de solo lectura: se calcula, no se escribe a mano.
- Solo se llena si estaba vacio, asi que un pedido ya registrado nunca pierde su valor original.
- El modulo trae un ``pre_init_hook`` que migra los identificadores externos del nombre viejo del
  modulo (``firstTimeOrder``) al actual. Es idempotente.

Known issues / Roadmap
======================

- **El campo almacenado se calcula desde un metodo decorado con ``@api.constrains`` en vez de
  ``@api.depends``.** Se midio en Odoo 19 que **funciona**: el campo se llena al crear el pedido y al
  escribir el disparador (``date_order``), que es el comportamiento que hay hoy en produccion. Aun
  asi no es la forma canonica de declarar un campo calculado almacenado. Cambiar el decorador
  recalcularia los datos historicos, asi que queda como decision pendiente del usuario.
- **Falta ``static/description/icon.png``.** En la ficha de Apps se ve el cubo generico de Odoo. Hace
  falta arte, no se inventa.

Credits
=======

Authors
-------

- David Tosse

Contributors
------------

- David Tosse
