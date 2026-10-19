==============================
POS - Configuración de comanda
==============================

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

Ajusta, **por punto de venta**, la comanda que el POS imprime en las impresoras de preparación
(cocina, barra). Es la plantilla ``point_of_sale.OrderChangeReceipt``, la misma que heredan
``pos_restaurant`` y ``pos_self_order``.

En Odoo 19 la comanda trae unos 96 px en blanco arriba (``pt-5 mt-5``) y 48 px abajo (``pb-5``) que en
Odoo 17 no existían y desperdician papel térmico. Además, en español (``es_419``) Odoo imprime
«Ordenar», «Por:» y «(DUPLICAR)». El módulo:

- **Quita ese espaciado** y lo deja configurable (0 a 100 px arriba y abajo; 0 por defecto).
- Permite **ocultar la línea del empleado** («Atendido por: …»).
- Permite **ocultar el número de pedido** («Pedido # N»). La referencia grande, que en restaurante
  lleva el **piso y la mesa**, se imprime siempre.
- Imprime las **etiquetas en español**: *Pedido*, *Atendido por:*, *NOTA INTERNA*,
  *NOTA DEL CLIENTE*, *(DUPLICADO !)*. Desmarcado, vuelve el texto de Odoo con su traducción.

No cambia qué se envía a cada impresora ni cuándo, ni el recibo del cliente.

**Table of contents**

.. contents::
   :local:

Configuration
=============

En *Punto de Venta › Configuración › Puntos de venta*, abrir la caja y, en la pestaña
**Configuración**, ir al bloque **Comanda de cocina**:

- **Espacio superior (px)** — 0 por defecto, de 0 a 100: blanco arriba de la comanda.
- **Espacio inferior (px)** — 0 por defecto, de 0 a 100: blanco al final del cuerpo.
- **Mostrar empleado** — marcado por defecto: línea «Atendido por: …».
- **Mostrar número de pedido** — marcado por defecto: línea «Pedido # N». No afecta al piso ni a
  la mesa.
- **Etiquetas en español** — marcado por defecto. Desmarcado, se usa el texto de Odoo en el idioma
  del usuario.

.. figure:: ../static/description/01_configuracion.png
   :alt: Punto de Venta › Configuración › Puntos de venta › (caja) › Configuración: bloque «Comanda de cocina»

   Punto de Venta › Configuración › Puntos de venta › (caja) › Configuración: bloque «Comanda de cocina»

Para imprimir comandas, la caja necesita al menos una impresora de preparación. Los cambios se
aplican la próxima vez que se carga el POS, y se pueden hacer con la sesión abierta.

Usage
=====

No hay nada que hacer en la caja: al enviar el pedido a cocina (*Enviar* en restaurante, o al
validar el pago en una caja sin mesas), la comanda sale con la configuración de esa caja. Con los
valores por defecto sale sin blanco arriba ni abajo y con las etiquetas en español, también en
la reimpresión (ícono de cubiertos) y en la comanda de notas:

.. figure:: ../static/description/02_comanda_por_defecto.png
   :alt: Comanda real con los valores por defecto: pedido, reimpresión y notas

   Comanda real con los valores por defecto: pedido, reimpresión y notas

Al ocultar el empleado o el número de pedido, el piso y la mesa siguen impresos:

.. figure:: ../static/description/03_comanda_opciones.png
   :alt: Comanda real con «Mostrar número de pedido» y «Mostrar empleado» desmarcados

   Comanda real con «Mostrar número de pedido» y «Mostrar empleado» desmarcados

Con **Etiquetas en español** desmarcado vuelve el texto de Odoo en el idioma del usuario:

.. figure:: ../static/description/04_comanda_etiquetas_core.png
   :alt: Comanda real con «Etiquetas en español» desmarcado

   Comanda real con «Etiquetas en español» desmarcado

El espacio superior e inferior se suma al papel impreso, sin cambiar el contenido:

.. figure:: ../static/description/05_comanda_espaciado.png
   :alt: Mismo pedido con espacio 0/0 y con 30/30 px

   Mismo pedido con espacio 0/0 y con 30/30 px

Known issues / Roadmap
======================

- «Guest: N» (comensales, de ``pos_restaurant``) es texto fijo en inglés del core y no se traduce;
  el módulo no lo toca.
- La comanda solo de notas no lleva la marca de duplicado al reimprimirse: así lo hace el core.

Credits
=======

Authors
-------

- Miguel Bolivar
- Libertario Coffee

Contributors
------------

- Miguel Bolivar
- Desarrollo Libertario \<<regionalit@libertariocoffee.com>\>
