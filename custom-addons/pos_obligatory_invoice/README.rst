==================
Obligatory Invoice
==================

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

Fuerza a facturar todos los pedidos de un punto de venta. Cada punto de venta
gana un interruptor, **Facturacion obligatoria** (``enable_obin``): cuando esta
activo, al abrir la pantalla de pago el pedido queda marcado para facturar sin
que el cajero toque nada, y si el cajero pulsa **Invoice** para desmarcarlo la
opcion vuelve a marcarse sola, con un aviso en pantalla.

Los puntos de venta que no tengan el interruptor activo siguen comportandose
como siempre: facturar sigue siendo opcional.

**Table of contents**

.. contents::
   :local:

Configuration
=============

*Ajustes > Punto de Venta*, bloque **Contabilidad**, casilla **Facturacion
obligatoria**. Es una configuracion **por punto de venta**: primero se elige el
punto de venta arriba y despues se marca la casilla. No olvidar **Guardar**.

Para que el cambio llegue a la caja **no alcanza con recargar** la pantalla del
POS: hay que volver a entrar desde el backend (boton *Continue Selling* /
*Open Register*).

Usage
=====

La casilla esta en los ajustes del punto de venta:

.. figure:: ../static/description/01_configuracion.png
   :alt: Casilla Facturacion obligatoria en los ajustes del punto de venta

   Casilla Facturacion obligatoria en los ajustes del punto de venta

Con el interruptor activo, cualquier pedido de ese punto de venta llega a la
pantalla de pago con **Invoice** ya marcado:

.. figure:: ../static/description/02_pantalla_pago.png
   :alt: Pantalla de pago del POS con la opcion Invoice marcada automaticamente

   Pantalla de pago del POS con la opcion Invoice marcada automaticamente

Si el cajero intenta desmarcarla, la opcion se restablece sola y el POS lo
avisa con el mensaje *"Este punto de venta exige facturar todos los pedidos."*:

.. figure:: ../static/description/03_no_se_puede_desmarcar.png
   :alt: Aviso del POS al intentar desmarcar la opcion Invoice

   Aviso del POS al intentar desmarcar la opcion Invoice

Los pedidos ya finalizados no se tocan: el modulo solo actua sobre el pedido en
curso.

Known issues / Roadmap
======================

- **Hace falta un diario de facturas.** Si el punto de venta no puede facturar
  (sin diario de facturas configurado en *Contabilidad > Diarios por defecto*),
  el modulo no fuerza nada: forzar el flag dejaria pedidos imposibles de
  validar.
- **Facturar exige cliente.** Odoo pide un cliente en el pedido antes de
  validar una venta facturada; con este modulo activo, todos los pedidos van a
  necesitarlo.
- Falta ``static/description/icon.png``. El modulo se publica sin icono propio.
- La configuracion es **por punto de venta**, no por compania ni global.
- El modulo se instala solo (``auto_install``) en cuanto esta *point_of_sale*.

Credits
=======

Authors
-------

- Osmar Toloza

Contributors
------------

- Osmar Toloza \<<desarrollo@libertariocoffee.com>\>
