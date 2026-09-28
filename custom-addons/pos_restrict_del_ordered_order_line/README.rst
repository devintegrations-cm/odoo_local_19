=============================
Restrict erase POS order line
=============================

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

Impide que un **empleado no autorizado** reduzca o borre una línea de pedido del Punto de Venta
después de enviarla a cocina. Cada punto de venta tiene una lista de empleados autorizados. Si el
empleado que tiene la caja está en la lista, puede reducir o borrar líneas como siempre. Si no está,
el POS rechaza la acción con el aviso *Operacion no permitida*.

Existe para que un mesero no pueda quitar de la cuenta un producto que la cocina ya está preparando
sin pasar por el líder de tienda.

Cada línea enviada muestra su **cantidad ordenada** con el distintivo *En preparación* y dos botones
para restar o sumar una unidad. Aumentar la cantidad siempre está permitido. Con la lista vacía,
todos los empleados pueden reducir y borrar líneas.

Está pensado para puntos de venta de tipo restaurante (depende de ``pos_restaurant``).

**Table of contents**

.. contents::
   :local:

Installation
============

Dependencias
------------

- ``pos_restaurant`` (Odoo Community), que trae ``point_of_sale``. No hay dependencias externas ni
  librerías de Python adicionales.
- ``pos_hr`` no es dependencia del módulo, pero hace falta en la práctica: el campo de Ajustes solo se
  ve con *Iniciar sesión como empleado* activo, y el control se evalúa sobre el empleado que inició
  sesión en la caja.

Pasos de instalación
--------------------

Instalar el módulo desde *Aplicaciones*. No crea modelos ni permisos de acceso: agrega un campo a la
configuración del punto de venta, un campo a las líneas de pedido y los archivos del POS. Después de
instalar o actualizar, hay que **volver a entrar al POS** desde el backend para que cargue los
archivos nuevos.

Migración desde Odoo 17
-----------------------

Los campos conservan el nombre técnico y la tabla de relación de Odoo 17:
``able_del_pol_employee_ids`` en ``pos.config`` (tabla ``abl_pol_employee_ids``) y ``ordered_quantities``
en ``pos.order.line``. La lista de empleados autorizados y las cantidades ordenadas de las órdenes
existentes se mantienen sin script de datos.

El archivo ``models/pos_session.py`` de 17 ya no existe: en Odoo 19 cada modelo declara sus campos
para el POS en ``_load_pos_data_fields``. El archivo ``security/ir.model.access.csv`` de 17 tampoco:
se refería a un modelo de otro módulo y el manifiesto de 17 no lo cargaba.

Configuration
=============

Ir a *Punto de venta › Configuración › Ajustes*, elegir el punto de venta en la parte superior y
buscar el bloque **Interfaz de PdV**.

.. figure:: ../static/description/01_configuracion.png
   :alt: Punto de venta › Configuración › Ajustes › Interfaz de PdV: Iniciar sesión como empleado y Borrar o reducir lineas de pedido POS

   Punto de venta › Configuración › Ajustes › Interfaz de PdV: Iniciar sesión como empleado y Borrar o reducir lineas de pedido POS

- **Iniciar sesión como empleado** (campo estándar de ``pos_hr``). Requisito. El campo del módulo
  solo aparece con esta casilla marcada y guardada, y el control usa el empleado que inició sesión
  en la caja.
- **Borrar o reducir lineas de pedido POS** (campo ``able_del_pol_employee_ids`` de ``pos.config``).
  Opcional; vacío por defecto. Lista de empleados de la compañía que pueden reducir o borrar líneas
  ya enviadas a cocina. Vacío significa que **todos** pueden.

A tener en cuenta:

- La configuración es **por punto de venta**. Hay que repetirla en cada tienda.
- Los cambios se ven en el POS después de volver a entrar a la sesión desde el backend.
- El texto de ayuda de la fila dice "borrar pedidos", pero este módulo **no controla la eliminación
  de órdenes completas**. Eso lo hace la fila **Borrar pedidos POS**, del módulo ``pos_del_order``.
- En el backend, la columna opcional **Ordered Quantities** de las líneas de la orden (*Punto de
  venta › Órdenes*) muestra la cantidad ordenada guardada. Es de solo lectura.

Usage
=====

Enviar a cocina
---------------

Al pulsar **Enviar** (o **Pago**, ver *Casos especiales*), el POS guarda la cantidad actual de cada
línea como **cantidad ordenada**. Al volver a la mesa, cada línea muestra esa cantidad entre los
botones de restar y sumar, con el distintivo *En preparación*.

.. figure:: ../static/description/02_linea_enviada.png
   :alt: Línea enviada a cocina con su cantidad ordenada y el distintivo En preparación

   Línea enviada a cocina con su cantidad ordenada y el distintivo En preparación

Empleado no autorizado
----------------------

Con un empleado que no está en la lista, cualquier intento de dejar la línea por debajo de la
cantidad ordenada muestra el aviso *Operacion no permitida* y la línea no cambia. Aplica a la tecla
⌫ del teclado numérico, a escribir una cantidad menor con el teclado y al botón de restar del
distintivo.

.. figure:: ../static/description/03_reduccion_denegada.png
   :alt: Empleado no autorizado: al pulsar ⌫ sobre la línea enviada, el POS lo impide

   Empleado no autorizado: al pulsar ⌫ sobre la línea enviada, el POS lo impide

Sumar unidades está permitido. Las unidades agregadas después del envío, mientras no se vuelva a
enviar, se pueden quitar hasta llegar otra vez a la cantidad ordenada.

Empleado autorizado
-------------------

Con un empleado de la lista, la línea se reduce o se borra como en el POS estándar. Odoo registra la
diferencia como un cambio pendiente para cocina (el botón **Enviar** muestra *Cocina -1*).

.. figure:: ../static/description/04_reduccion_autorizada.png
   :alt: Empleado autorizado: la cantidad baja a 1 y el distintivo conserva la cantidad ordenada

   Empleado autorizado: la cantidad baja a 1 y el distintivo conserva la cantidad ordenada

El distintivo sigue mostrando la cantidad ordenada anterior hasta el próximo **Enviar**, que la
actualiza con la cantidad nueva.

Casos especiales
----------------

- **Lista vacía**: todos los empleados pueden reducir y borrar líneas.
- **Cambio de empleado**: la regla se evalúa con el empleado que tiene la caja en ese momento. Al
  bloquear la caja y entrar con otro PIN, el mismo pedido queda permitido o bloqueado según el
  nuevo empleado.
- **Pago**: el botón **Pago** también marca todas las líneas como ordenadas, antes de que Odoo
  pregunte si se quiere enviar el pedido a preparación. Aunque se elija *Descartar* y no se envíe
  nada a cocina, al volver a la mesa las líneas aparecen *En preparación* y quedan protegidas.
- **Dividir cuenta**: al confirmar la división, las cantidades de las dos órdenes resultantes pasan
  a ser las cantidades ordenadas.
- **Combos**: si alguna línea del combo tiene cantidad ordenada, el empleado no autorizado no puede
  borrar el combo.
- **Transferir o fusionar mesas, Cancelar orden, Liberar la mesa**: no pasan por este control (ver
  *Limitaciones conocidas*).

Solución de problemas
---------------------

- **No aparece el campo en Ajustes.** Marcar *Iniciar sesión como empleado*, guardar y volver a la
  página: el campo está dentro de ese bloque.
- **La línea no muestra el distintivo *En preparación*.** Solo aparece después de **Enviar** o
  **Pago**, en las pantallas de productos y de pago, y nunca en líneas de recompensa. Si el módulo
  se acaba de instalar, volver a entrar al POS desde el backend.
- **Un empleado no autorizado puede reducir la línea.** Verificar que la lista esté guardada en el
  punto de venta correcto, volver a entrar al POS y revisar qué empleado tiene la caja (avatar arriba
  a la derecha). Si la reducción no baja de la cantidad ordenada, está permitida.
- **Un empleado no puede quitar un producto que nunca se envió a cocina.** Probablemente se pulsó
  **Pago** antes (ver *Casos especiales*). Lo puede quitar un empleado autorizado.

Known issues / Roadmap
======================

Limitaciones conocidas
----------------------

- **El control vive en el navegador.** No hay validación en el servidor: ``ordered_quantities`` es
  escribible y quien envíe la orden por RPC puede cambiar cantidades o borrar líneas. Si el POS no
  terminó de cargar, el módulo deja pasar la acción.
- **Pago marca líneas no enviadas.** El parche de ``PosStore.pay()`` guarda las cantidades ordenadas
  antes de que ``pos_restaurant`` pregunte si se envía el pedido, así que *Descartar* no lo evita. En
  Odoo 17 el botón de pago llamaba a ``order.pay()`` y no marcaba líneas: es un cambio de
  comportamiento de la migración.
- **Flujos de Odoo que no pasan por el control.** El módulo intercepta ``setQuantity``,
  ``removeOrderline`` y ``updateQuantityNumber``. No quedan restringidos: *Transferir / Fusionar* mesas
  (si la línea se suma a otra existente, la cantidad ordenada de origen no se suma), *Cancelar orden*
  y *Liberar la mesa* (eliminan la orden entera; para eso está ``pos_del_order``) ni la división de
  cuenta.
- **La cantidad ordenada no baja con una reducción autorizada.** Queda en el valor anterior hasta el
  próximo envío o pago.
- **Sin "Iniciar sesión como empleado" la regla compara ids distintos.** ``getCashier()`` devuelve el
  usuario (``res.users``) y el módulo compara su id con ids de empleados. El campo se oculta en Ajustes
  en ese caso, pero el valor guardado se conserva y sigue aplicando.
- El texto de ayuda de Ajustes menciona "borrar pedidos", que es la función de ``pos_del_order``.
- Los textos están en español en el código; el aviso usa ``_t`` pero el módulo no trae archivos de
  traducción. El título *Operacion no permitida* va sin tilde.
- ``static/description/icon.png`` mide 750x750 px; la norma pide 100x100 como los módulos del core.
- No hay tests automáticos.

Componentes
-----------

- ``models/pos_config.py``: el campo ``able_del_pol_employee_ids`` (Many2many a ``hr.employee``, tabla
  ``abl_pol_employee_ids``).
- ``models/res_config_settings.py``: el campo relacionado ``pos_able_del_pol_employee_ids``, escribible,
  que usa la pantalla de Ajustes.
- ``models/pos_order.py``: el campo ``ordered_quantities`` de ``pos.order.line`` y su alta en
  ``_load_pos_data_fields`` para que viaje al POS y se guarde al sincronizar.
- ``views/res_config_settings_views.xml``: la fila de Ajustes, dentro del bloque
  ``multiple_employee_session`` de ``pos_hr``.
- ``views/pos_order_view.xml``: la columna opcional *Ordered Quantities* en las líneas de la orden.
- ``static/src/js/models.js``: parches de ``PosOrderline.setQuantity()``, ``PosOrder.removeOrderline()``
  y ``OrderSummary.updateQuantityNumber()``, y la regla ``isCapableToDeletePosOrderLines()``.
- ``static/src/js/pos_store.js``: parche de ``PosStore.submitOrder()`` y ``PosStore.pay()`` que guarda las
  cantidades ordenadas, y expone el store a los modelos (``posRestrictState``).
- ``static/src/js/split_bill_screen.js``: parche de ``SplitBillScreen.createSplittedOrder()``.
- ``static/src/js/orderline.js``, ``static/src/xml/orderline.xml``, ``static/src/css/orderline.scss``: el
  distintivo *En preparación* con los botones de restar y sumar.

Notas para mantenimiento
------------------------

- **Qué es "línea ordenada".** Es el campo propio ``ordered_quantities``, no un concepto de Odoo. No
  coincide con ``uiState.savedQuantity`` (cantidad sincronizada) ni con
  ``last_order_preparation_change`` (lo que Odoo ya notificó a cocina).
- **El parche de ``updateQuantityNumber`` hoy no se ejecuta.** Ese camino solo se usa cuando
  ``PosStore.disallowLineQuantityChange()`` devuelve ``true``; en Odoo 19 Community devuelve ``false`` y
  ningún módulo de Community lo cambia. Queda como defensa si se instala uno que lo active.
- **Cambio respecto de Odoo 17.** El envío a cocina pasó de ``ActionpadWidget.submitOrder()`` a
  ``PosStore.submitOrder()``, la división de ``proceed()`` a ``createSplittedOrder()``, y el aviso de
  ``ErrorPopup`` a ``AlertDialog``. En 19 ``setQuantity`` devuelve el error y quien la llama muestra el
  diálogo; el borrado con ⌫ va directo a ``removeOrderline``, por eso hay dos parches.
- **El identificador de la vista de Ajustes** (``res_config_settings_view_form_inh_pos_del_order_17``)
  viene de 17 y menciona ``pos_del_order``, pero pertenece a este módulo. No renombrarlo sin revisar
  el efecto en la actualización.

Credits
=======

Authors
-------

- Libertario Coffee Roasters

Contributors
------------

- Libertario Coffee Roasters, equipo de desarrollo
- Cristian Mira (migración a Odoo 19)
