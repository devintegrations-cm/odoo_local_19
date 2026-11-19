====================================
POS Partner Performance - Settle Due
====================================

..
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! Generado a partir de los fragmentos de readme/      !!
   !! Los cambios se sobrescriben: editar readme/*.md     !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1| |badge2|

Puente entre ``pos_partner_performance`` y ``pos_settle_due`` (Enterprise, *Liquidar deudas* en el POS).
Deja de calcular la **deuda de cada cliente** en el POS.

``pos_settle_due`` calcula la deuda (órdenes y facturas pendientes) de cada cliente que carga el POS:

- al cargar los clientes del POS: ~60 s por página de 100 clientes (medido en staging);
- al abrir la caja, otra vez para todos los clientes cargados;
- después de cada búsqueda de clientes: hasta 27 s por búsqueda;
- después de cada venta pagada con *cuenta de cliente* (convenios): 20–46 s por venta.

El costo crece con la historia del cliente, no con lo que debe. El peor caso son los **clientes
por defecto** de cada tienda (*VENTA MOSTRADOR …*), que se cargan siempre: el de Zona G tiene
145.387 órdenes y 138.984 facturas, y solo su ``total_due`` tardó **37,7 s**, dos veces en cada
apertura de la caja.

En las cajas con **No calcular la deuda de los clientes** activado (por defecto):

- los clientes llegan al POS sin la deuda, y no se vuelve a pedir al abrir la caja ni al buscar;
- después de una venta con cuenta de cliente tampoco se recalcula (``pos_settle_due`` solo lo hace si
  el cliente trae la deuda cargada).

Las deudas las gestiona Contabilidad en el backend; en el POS no se liquidan.

**Table of contents**

.. contents::
   :local:

Installation
============

No se instala a mano: Odoo lo instala solo cuando están instalados ``pos_partner_performance`` **y**
``pos_settle_due``. Desinstalar ``pos_partner_performance`` lo desinstala.

**Solo funciona en bases con Enterprise** (staging y producción): depende de ``pos_settle_due``, que
no existe en la base local Community. Es la única excepción a la regla del proyecto de no depender
de módulos Enterprise, y por eso vive en un módulo aparte: para que ``pos_partner_performance`` se
pueda instalar y probar en local. La carpeta tiene que estar en el código del servidor aunque no se
instale a mano.

Después de instalar, en cada caja: menú ☰ → **Recargar datos**.

Configuration
=============

Por caja, en *Punto de venta › Configuración › Punto de venta* → la caja → pestaña
**Configuración**:

- **No calcular la deuda de los clientes** (``skip_partner_due``). Activado por defecto en todas las
  cajas al instalar. Desmarcado, la caja vuelve al comportamiento estándar de *Liquidar deudas*.

El POS toma el cambio al volver a cargar los datos (menú ☰ → **Recargar datos**).

Usage
=====

No hay nada que hacer en la caja. Con la opción activada, la lista de clientes del POS (en las cajas
donde está visible) ya no muestra *Total adeudado* ni las opciones *Liquidar órdenes* / *Liquidar
facturas*: ``pos_settle_due`` las muestra solo cuando conoce una deuda mayor que cero, y ahora no la
calcula.

La deuda de un cliente se consulta en el backend (*Contabilidad*, ficha del contacto).

Known issues / Roadmap
======================

Limitaciones conocidas
----------------------

- **No hay control de límite de crédito en el POS** en las cajas con la opción activada:
  ``pos_settle_due`` bloquea la venta a un cliente que supera su límite usando la deuda cargada. Hoy
  no aplica: la compañía tiene desactivado el límite de crédito (``account_use_credit_limit``) y
  ningún contacto tiene límite (verificado en staging, 2026-11-18). Si se activa, desmarcar la
  opción en las cajas que lo necesiten.
- **No se puede probar en local** (no hay ``pos_settle_due``): se prueba en staging.
- **Depende del código de ``pos_settle_due``** (``setAllTotalDueOfPartners``, ``get_all_total_due``, la
  condición ``total_due !== undefined`` del recálculo tras la venta y los campos ``total_due``,
  ``invoices_amount_due`` y ``pos_orders_amount_due``). Si una actualización de Enterprise los cambia,
  la intercepción dejaría de funcionar **sin dar error**. Para evitarlo, los tests del módulo
  comprueban que todo eso sigue existiendo y fallan si no: correrlos en staging después de cada
  actualización de Enterprise.

Changelog
=========

19.0.1.0.0
----------

- Primera versión: sin deuda en la carga de clientes y sin cálculo de la deuda de todos los
  clientes al abrir la caja ni al buscar, activable por caja.

Credits
=======

Authors
-------

- Miguel Bolivar
- Libertario Coffee

Contributors
------------

- Miguel Bolivar
