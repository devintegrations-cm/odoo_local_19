==================
POS Limit Products
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

De fábrica, todo producto marcado como **Point of Sale** aparece en la pantalla de productos
de **todas** las cajas de la compañía. Con varios locales en la misma base —una tienda, un
restaurante, un kiosco— el cajero termina viendo un catálogo que no vende.

Este módulo agrega al producto el campo **Puntos de venta**. El punto de venta carga y
muestra solo los productos que lo tienen a él en ese campo. No hay ajuste que activar ni
pantalla de configuración aparte: la relación se define producto por producto y rige de
inmediato en la siguiente apertura de la sesión. Funciona sobre Odoo 19.0.

**Table of contents**

.. contents::
   :local:

Configuration
=============

El módulo no agrega ajustes al punto de venta ni a los Ajustes generales: toda la
configuración es la asignación de cada producto a sus cajas.

- Entrá a *Punto de Venta › Productos › Productos*.
- Abrí el producto y pasá a la pestaña **Point of Sale**.
- Junto a la categoría del POS está el campo **Puntos de venta**: agregá las cajas que tienen
  que mostrar ese producto.
- Guardá.

La pestaña **Point of Sale** solo existe si el producto tiene tildada la casilla **Point of
Sale** de la cabecera. Esa casilla es del núcleo de Odoo, no de este módulo, y es la que
habilita el producto para el punto de venta.

Después de cambiar las asignaciones no alcanza con recargar la pestaña del POS: hay que
volver a entrar al punto de venta desde el backend (*Abrir caja* / *Continue Selling*) para
que la sesión cargue la nueva lista de productos.

Usage
=====

La asignación se hace en la ficha del producto, pestaña **Point of Sale**, campo **Puntos de
venta**.

.. figure:: ../static/description/01_configuracion.png
   :alt: Formulario de producto, pestaña Point of Sale, con el campo Puntos de venta resaltado

   Formulario de producto, pestaña Point of Sale, con el campo Puntos de venta resaltado

El cajero no hace nada distinto: abre su caja y la grilla ya viene recortada. En el ejemplo,
el punto de venta **Kiosk** tenía asignados los 40 productos de la base de demostración
—muebles, ropa, panadería y bebidas, todo junto—.

.. figure:: ../static/description/02_pos_antes.png
   :alt: Pantalla de productos del punto de venta Kiosk con los 40 productos asignados

   Pantalla de productos del punto de venta Kiosk con los 40 productos asignados

Se le quitó el punto de venta **Kiosk** del campo **Puntos de venta** a todo lo que no fuera
pastelería ni bebidas, y se volvió a entrar a la misma caja. Quedan diez productos, y las
categorías vacías también desaparecen de la barra superior.

.. figure:: ../static/description/03_pos_filtrado.png
   :alt: La misma pantalla de productos mostrando solo los diez productos asignados al punto de venta

   La misma pantalla de productos mostrando solo los diez productos asignados al punto de venta

Known issues / Roadmap
======================

- **Requisito de despliegue: asigná productos antes de instalar.** Con el módulo instalado, un
  punto de venta que no tenga ni un producto asignado **deja de abrir**: el intento termina en
  un error (*«There is no product linked to your PoS»*, que desde el navegador se ve como un
  error 422). Antes de instalarlo en producción hay que recorrer todas las cajas y dejar cada
  una con su lista de productos.
- **El filtro es visual.** Oculta de la pantalla de productos lo que no corresponde a esa
  caja, pero no impide que un producto ajeno llegue al pedido por otras vías del núcleo de
  Odoo: un ítem de combo, un pedido ya abierto en una mesa, un código de barras. Es
  deliberado: esos productos tienen que seguir cargados en la sesión, porque quitarlos del
  todo dejaría sin registro a los pedidos en curso y rompería la mesa. El objetivo del módulo
  es que el cajero no vea lo que no vende, no bloquear la venta.
- **Convive con el límite de categorías del núcleo.** Si el punto de venta tiene categorías
  restringidas en sus ajustes, se aplican los dos filtros a la vez: se muestra lo que esté
  asignado a esa caja *y* pertenezca a una categoría permitida.
- **El campo es por plantilla de producto.** Todas las variantes de un producto siguen la
  asignación de su plantilla; no se puede habilitar una variante en una caja y otra en otra.
- Falta ``static/description/icon.png``: el módulo se muestra con el icono genérico de Odoo.

Credits
=======

Authors
-------

- Roaya

Contributors
------------

- `Roaya <https://www.roayadm.com>`_
