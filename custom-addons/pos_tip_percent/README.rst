==================
POS Tip Percentage
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

Reemplaza el botón **Propina** de la pantalla de **Pago** del Punto de Venta por hasta **tres botones
de porcentaje** configurables por punto de venta (por ejemplo, 5 %, 10 % y 20 %). Al pulsar uno, el
POS calcula la propina sobre el subtotal de la orden y la agrega como una línea del producto de
propina, sin que el cajero tenga que hacer la cuenta ni escribir el valor.

Relación con Odoo 19: la propina es del núcleo (``point_of_sale``). Odoo trae un solo botón
**Propina** que abre un teclado para escribir el valor a mano. Este módulo no cambia cómo se guarda
la propina: usa el mismo producto de propina y el mismo método del núcleo (``setTip``), así que la
línea de propina y el total quedan igual que con el botón estándar.

Cómo se calcula, según el código (``static/src/js/pos_payment.js``):

- **Base: subtotal sin impuestos y sin la propina actual.** Total con impuestos, menos impuestos,
  menos la propina que ya tenga la orden. En la captura de *Uso*, dos hamburguesas suman $ 66.640
  con $ 10.640 de impuestos; la base es $ 56.000 y el 10 % da $ 5.600.
- **Redondeo a unidades enteras** de la moneda (``Math.round``). En pesos colombianos no se nota; en
  una moneda con centavos, la propina pierde los decimales.
- **Un solo valor de propina por orden.** Pulsar otro porcentaje reemplaza el anterior; no se suman.

**Table of contents**

.. contents::
   :local:

Installation
============

Dependencias
------------

- ``point_of_sale`` (Odoo 19 Community). No hay otras dependencias ni librerías de Python adicionales.

Pasos de instalación
--------------------

Instalar *POS Tip Percentage* desde *Aplicaciones*. El módulo agrega cuatro campos a la
configuración del punto de venta, un ajuste en *Punto de venta › Configuración › Ajustes* y un
archivo JavaScript y una plantilla al POS. No crea menús, modelos ni permisos. Después de instalar o
actualizar, **volver a entrar al POS** desde el backend para que cargue los archivos nuevos.

Migración desde Odoo 17
-----------------------

- Los campos conservan su nombre técnico en ``pos.config`` (``iface_tippercent``, ``tip_percent1``,
  ``tip_percent2``, ``tip_percent3``), así que los porcentajes configurados en la 17 se mantienen sin
  script de datos.
- La 17 traía restos de un modelo ``pos.tip`` que ya no se usaba: un controlador ``/pos/tip/name`` y una
  línea de permisos. En la 19 se quitaron; el modelo ya estaba comentado en la 17.
- En la 17 la casilla estaba dentro del ajuste *Propinas*. En la 19 es un ajuste aparte, justo
  después de *Propinas*, y solo se ve con *Propinas* activado.

Configuration
=============

Ir a *Punto de venta › Configuración › Ajustes*, elegir el punto de venta en la parte superior y
buscar el bloque **Pago**. El ajuste del módulo está justo después del ajuste **Propinas** de Odoo.

.. figure:: ../static/description/01_configuracion.png
   :alt: Punto de venta › Configuración › Ajustes › Pago: Propinas de Odoo y botones de porcentaje del módulo

   Punto de venta › Configuración › Ajustes › Pago: Propinas de Odoo y botones de porcentaje del módulo

- **Propinas** (Odoo, campo ``iface_tipproduct``). Obligatorio. Sin él no se ve el ajuste del módulo.
  Al activarlo, Odoo propone el **Producto de propina** (``tip_product_id``); en esta base es
  *[TIPS] Propinas*. El módulo usa ese producto para la línea de propina.
- **Add buttons with percentage for tip** (campo ``iface_tippercent`` de ``pos.config``). Obligatorio
  para que el módulo actúe; desmarcado por defecto. Al marcarlo aparecen los tres porcentajes.
- **Tip % (Option 1)**, **(Option 2)** y **(Option 3)** (campos ``tip_percent1``, ``tip_percent2`` y
  ``tip_percent3``). Opcionales; 0 por defecto. Cada porcentaje distinto de 0 es un botón en la
  pantalla de pago. Un porcentaje en 0 no muestra botón.

A tener en cuenta:

- **Con el módulo instalado, *Propinas* solo no alcanza.** El módulo reemplaza el botón estándar
  **Propina** de la pantalla de pago. Si *Propinas* está activado pero *Add buttons with percentage
  for tip* no, la pantalla de pago queda **sin ningún botón de propina**.
- Si la casilla está marcada y los tres porcentajes están en 0, se ve un único botón **Propina** que
  abre el teclado de Odoo, como el estándar.
- Al desmarcar *Propinas* en Ajustes, Odoo deja vacío el producto de propina y los botones del
  módulo desaparecen, aunque su casilla siga marcada.
- La configuración es **por punto de venta**. Hay que repetirla en cada tienda.
- Los cambios se ven en el POS después de volver a entrar a la sesión desde el backend.
- *Agregar propina después del pago* es otra función de Odoo (restaurante) y no interviene en este
  módulo.

Usage
=====

Flujo
-----

En el POS, cargar la orden y pulsar **Pago**. Debajo de los métodos de pago aparecen los botones
**Propina N %**, uno por cada porcentaje configurado.

.. figure:: ../static/description/02_botones_pago.png
   :alt: Pantalla de pago con los tres botones de porcentaje

   Pantalla de pago con los tres botones de porcentaje

Pulsar el porcentaje que pide el cliente. El POS agrega la propina a la orden y el total a pagar
sube en ese valor. El botón elegido queda resaltado y, desde ese momento, cada botón muestra cuánto
sería la propina con su porcentaje, para comparar antes de cambiar.

.. figure:: ../static/description/03_propina_aplicada.png
   :alt: Propina del 10 % aplicada: botón resaltado, valor de cada opción y total con propina

   Propina del 10 % aplicada: botón resaltado, valor de cada opción y total con propina

Después se elige el método de pago y se valida como siempre. La propina es una línea más de la
orden, con el producto de propina, y se ve al volver a la pantalla de productos con **Regresar**.

.. figure:: ../static/description/05_linea_propina.png
   :alt: Orden con la línea del producto de propina y el total actualizado

   Orden con la línea del producto de propina y el total actualizado

Casos especiales
----------------

- **Cambiar de porcentaje.** Pulsar otro botón reemplaza la propina anterior; la orden conserva una
  sola línea de propina. En la prueba: 10 % ($ 5.600), luego 20 % ($ 11.200), luego 5 % ($ 2.800).
- **Pulsar dos veces el mismo botón** no suma nada: la propina se calcula sin la anterior y da el
  mismo valor.
- **Con una línea de pago ya cargada.** Si la línea seleccionada es de efectivo u otro método no
  electrónico, o un pago electrónico todavía pendiente, su monto se ajusta por la diferencia de
  propina. En la captura, la línea de efectivo tenía el total con 20 % ($ 77.840) y bajó a
  $ 69.440 al cambiar a 5 %. Un pago electrónico ya enviado no se toca.

.. figure:: ../static/description/04_ajuste_pago.png
   :alt: Cambio de 20 % a 5 % con una línea de efectivo cargada: la línea se ajusta sola

   Cambio de 20 % a 5 % con una línea de efectivo cargada: la línea se ajusta sola

- **Orden sin productos o porcentaje que da 0**: el botón no hace nada.
- **Quitar la propina.** El módulo no trae un botón para quitarla. Hay que borrar la línea del
  producto de propina en la pantalla de productos.
- **Propina con un valor libre.** Mientras haya algún porcentaje configurado, la pantalla de pago no
  ofrece el teclado de Odoo para escribir el valor: ese botón solo aparece con los tres porcentajes
  en 0.

Solución de problemas
---------------------

- **No aparece ningún botón de propina en Pago.** Revisar que *Propinas* esté activado con un
  producto de propina y que *Add buttons with percentage for tip* esté marcado (ver
  *Configuración*). Después, volver a entrar al POS desde el backend.
- **Falta uno de los botones.** Ese porcentaje está en 0.
- **La propina parece menor de lo esperado.** Se calcula sobre el subtotal **sin impuestos**, no
  sobre el total que ve el cliente.
- **Los botones no muestran el valor.** Es normal antes de aplicar la primera propina: los valores
  aparecen cuando la orden ya tiene propina.

Known issues / Roadmap
======================

Limitaciones conocidas
----------------------

- **Oculta el botón estándar de propina.** La plantilla reemplaza el botón *Propina* de Odoo, y los
  botones nuevos solo salen con la casilla del módulo marcada. Con el módulo instalado y la casilla
  desmarcada, no hay forma de agregar propina desde la pantalla de pago. Es el mismo comportamiento
  de la 17.
- **Redondeo a enteros.** ``Math.round`` quita los decimales de la propina. Correcto para pesos
  colombianos; en una moneda con centavos no lo sería.
- **Resaltado por monto.** Un botón se resalta si la propina de la orden es igual a su valor. Si
  dos porcentajes dan el mismo monto (por ejemplo, en órdenes muy chicas), se resaltan los dos.
- Los valores de cada botón solo se muestran cuando la orden ya tiene propina.
- Los textos del ajuste (*Add buttons with percentage for tip*, *Tip % (Option 1)*...) están en
  inglés y el módulo no trae traducciones. En el POS el botón sale como *Propina* porque usa la
  palabra *Tip*, que ya traduce Odoo.
- El ajuste se puede cambiar con la sesión abierta, pero el POS lo toma recién al volver a entrar.
- No hay tests automáticos. El comportamiento del POS se valida a mano en el navegador.
- Falta ``static/description/icon.png``: en *Aplicaciones* se ve el ícono genérico de Odoo.

Componentes
-----------

- ``models/pos_order.py``: pese al nombre, hereda ``pos.config`` y agrega ``iface_tippercent``,
  ``tip_percent1``, ``tip_percent2`` y ``tip_percent3``.
- ``models/res_config_settings.py``: los campos relacionados en Ajustes, con prefijo ``pos_`` porque
  ``res.config.settings`` es compartido por todos los módulos.
- ``views/pos_order.xml``: el ajuste, insertado después de ``setting[@id='iface_tipproduct']`` y
  visible solo con *Propinas* activado.
- ``static/src/xml/pos_payment.xml``: hereda ``point_of_sale.PaymentScreenButtons`` y reemplaza el
  botón ``addTip`` por los botones de porcentaje (o por un botón *Propina* equivalente al estándar si
  los tres porcentajes están en 0).
- ``static/src/js/pos_payment.js``: parche de ``PaymentScreen`` con ``addTip1..3``, ``getTipX``
  (cálculo), ``shouldHighlight`` (resaltado) y ``addTipPercent``, que llama a ``this.pos.setTip()`` del
  núcleo y ajusta la línea de pago seleccionada.
- Los campos llegan al POS sin cargador propio: ``pos.config`` no define ``_load_pos_data_fields`` y el
  POS lee todos sus campos.

Notas para mantenimiento
------------------------

- **Depende del botón del núcleo.** El XPath busca ``//button[@t-on-click='addTip']`` en
  ``PaymentScreenButtons``. Si Odoo cambia ese botón, la herencia falla al cargar el POS.
- **API del núcleo usada**: ``order.priceIncl``, ``order.amountTaxes``, ``order.getTip()``,
  ``pos.setTip()``, ``paymentLine.isElectronic()``, ``getPaymentStatus()``, ``getAmount()`` y
  ``setAmount()``. En la 17 se llamaban ``get_total_with_tax``, ``get_total_tax``, ``get_tip`` y
  ``set_tip``.
- **Diferencia con la 17.** En la 17 el módulo ponía la propina en 0 y la volvía a calcular, sin
  tocar las líneas de pago. En la 19 copia el comportamiento del botón estándar ``addTip``: ajusta la
  línea de pago seleccionada por la diferencia. El valor de la propina calculado es el mismo.
- ``getTip()`` devuelve la propina sin impuestos; la base resta la propina sin impuestos del subtotal.
  Si el producto de propina tuviera impuestos, el cálculo seguiría siendo sobre la base sin
  impuestos de los demás productos.

Credits
=======

Authors
-------

- Roaya

Contributors
------------

- Roaya (autor original)
- Libertario Coffee
- Cristian Mira (migración a Odoo 19)
