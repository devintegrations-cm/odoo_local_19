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

- **Base: subtotal sin impuestos y sin la propina actual** (configurable: *Total con impuestos*).
  Total sin impuestos de la orden menos la propina que ya tenga. En la captura de *Uso*, dos hamburguesas suman $ 66.640
  con $ 10.640 de impuestos; la base es $ 56.000 y el 10 % da $ 5.600.
- **Redondeo a unidades enteras** por defecto (``tip_percent_decimals`` = 0), como en la 17.
- **Un solo valor de propina por orden.** Pulsar otro porcentaje reemplaza el anterior; no se suman.
- **No toca las líneas de pago**, igual que en la 17: si ya hay efectivo cargado, el cambio baja en el
  valor de la propina; si falta plata, la orden muestra el saldo pendiente.

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

Instalar *POS Tip Percentage* desde *Aplicaciones*. El módulo agrega seis campos a la
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
- 19.0.1.1.0 adopta la versión de Costa Rica y México: campos nuevos ``tip_percent_base`` y
  ``tip_percent_decimals`` (los valores por defecto dan el cálculo de la 17, sin script de datos) y el
  botón ya no modifica la línea de pago (corrige el descuadre de caja con cambio, C5).

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
- **Base del calculo** (campo ``tip_percent_base``). *Total sin impuestos* (por defecto, igual que en
  la 17) o *Total con impuestos*. En ambos casos se descuenta la propina ya cargada.
- **Decimales** (campo ``tip_percent_decimals``, 0 a 6). 0 por defecto: redondea a la unidad, igual que
  en la 17.

A tener en cuenta:

- El botón estándar **Propina** de Odoo (teclado para escribir el valor) se oculta solo cuando la
  casilla del módulo está marcada y hay al menos un porcentaje distinto de 0. En cualquier otro caso
  se ve el botón estándar. En la 17, con *Propinas* activado y la casilla desmarcada, no quedaba
  ningún botón de propina; en staging las 16 cajas con *Propinas* tienen también la casilla marcada.
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
sube en ese valor. El botón elegido queda resaltado; cada botón muestra cuánto sería la propina con
su porcentaje.

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
- **Con una línea de pago ya cargada.** El botón no modifica la línea de pago (como en la 17). Si
  el cliente entregó más efectivo que el total, el cambio baja en el valor de la propina; si la
  línea quedó corta, la orden muestra el saldo pendiente y el cajero ajusta el monto. Ejemplo:
  total $ 10.000, efectivo $ 20.000, propina 10 % ($ 1.000): pago $ 20.000 y cambio $ 9.000.

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

Known issues / Roadmap
======================

Limitaciones conocidas
----------------------

- **Oculta el botón estándar de propina** cuando hay porcentajes configurados: no se puede escribir
  un valor libre en esas cajas.
- **Redondeo a enteros** por defecto; se ajusta con *Decimales*.
- **Resaltado por monto.** Un botón se resalta si la propina de la orden es igual a su valor. Si
  dos porcentajes dan el mismo monto (por ejemplo, en órdenes muy chicas), se resaltan los dos.
- Los textos del ajuste (*Add buttons with percentage for tip*, *Tip % (Option 1)*...) están en
  inglés y el módulo no trae traducciones. En el POS el botón sale como *Propina* porque usa la
  palabra *Tip*, que ya traduce Odoo.
- El ajuste se puede cambiar con la sesión abierta, pero el POS lo toma recién al volver a entrar.
- No hay tests automáticos. El comportamiento del POS se valida a mano en el navegador.
- Falta ``static/description/icon.png``: en *Aplicaciones* se ve el ícono genérico de Odoo.

Componentes
-----------

- ``models/pos_order.py``: pese al nombre, hereda ``pos.config`` y agrega ``iface_tippercent``,
  ``tip_percent1``, ``tip_percent2``, ``tip_percent3``, ``tip_percent_base`` y ``tip_percent_decimals``.
- ``models/res_config_settings.py``: los campos relacionados en Ajustes, con prefijo ``pos_`` porque
  ``res.config.settings`` es compartido por todos los módulos.
- ``views/pos_order.xml``: el ajuste, insertado después de ``setting[@id='iface_tipproduct']`` y
  visible solo con *Propinas* activado.
- ``static/src/xml/pos_payment.xml``: hereda ``point_of_sale.PaymentScreenButtons``, oculta el botón
  ``addTip`` cuando hay porcentajes y agrega los botones de porcentaje a continuación.
- ``static/src/js/pos_payment.js``: parche de ``PaymentScreen`` con ``addTip1..3``, ``getTipBase``,
  ``roundTip``, ``getTipX`` (cálculo), ``shouldHighlight`` (resaltado) y ``addTipPercent``, que solo llama a
  ``this.pos.setTip()`` del núcleo.
- Los campos llegan al POS sin cargador propio: ``pos.config`` no define ``_load_pos_data_fields`` y el
  POS lee todos sus campos.

Notas para mantenimiento
------------------------

- **Depende del botón del núcleo.** El XPath busca ``//button[@t-on-click='addTip']`` en
  ``PaymentScreenButtons``. Si Odoo cambia ese botón, la herencia falla al cargar el POS.
- **API del núcleo usada**: ``order.priceIncl``, ``order.priceExcl``, ``line.prices``, ``pos.setTip()``,
  ``pos.currency.round/isZero/equal`` y ``roundDecimals`` de ``@web/core/utils/numbers``.
- **Igual que en la 17, no toca las líneas de pago.** La versión anterior de la 19 copiaba el botón
  estándar ``addTip`` y sumaba la propina a la línea seleccionada sin descontar el cambio: con
  efectivo y cambio, el pago registrado superaba lo recibido (POS-TIP-PERCENT-FE-0001).
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
