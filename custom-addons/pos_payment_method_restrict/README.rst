===========================
POS Payment Method Restrict
===========================

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

Permite reservar métodos de pago del Punto de Venta para **clientes autorizados**. En cada punto de
venta se define una lista de restricciones: cada una asocia un método de pago con los clientes que
pueden usarlo. En la pantalla de pago:

- un cliente con restricción ve **solo** los métodos que tiene autorizados;
- cualquier otro cliente, o una orden sin cliente, ve solo los métodos que no están restringidos.

Cada restricción puede además:

- pedir **datos adicionales** en un popup al elegir el método (por ejemplo huésped y habitación) y
  avisar si hoy ya se registró una orden con los mismos datos;
- decidir si la orden **se factura en el POS o no**, por encima de la facturación obligatoria;
- forzar la **entrega de inventario** en el momento de la venta.

Las órdenes que quedan sin factura se facturan después en una sola **factura agrupada** por cliente,
desde la lista de órdenes. El menú *Reportes › Convenios y restricciones* muestra las órdenes con
los datos capturados.

El caso que lo originó es el convenio de desayunos con un hotel: el huésped no paga, la orden queda
a nombre del hotel con los datos del huésped y se factura al hotel al cierre del mes.

**Table of contents**

.. contents::
   :local:

Installation
============

Dependencias
------------

- ``point_of_sale``. No hay otras dependencias de Odoo ni librerías de Python adicionales.

Pasos de instalación
--------------------

Instalar el módulo desde *Aplicaciones*. Crea dos modelos (``pos.payment.customer.restriction`` y
``pos.payment.restriction.field``) con estos permisos: el grupo *Punto de venta / Administrador* puede
crear, editar y borrar; el grupo *Punto de venta / Usuario* solo leer, que es lo que necesita el
POS. Después de instalar o actualizar, hay que **volver a entrar al POS** desde el backend para que
cargue los archivos nuevos.

Migración desde Odoo 17
-----------------------

Los modelos, los campos y la tabla de clientes autorizados (``pos_payment_restrict_partner_rel``)
conservan el nombre técnico de la versión 17, así que las restricciones existentes se mantienen sin
script de datos.

Al actualizar desaparece la acción *Crear factura electrónica agrupada*: dependía del diario
electrónico del POS (``electronic_invoice_journal_id``), que Jorels 19 eliminó. Tampoco se porta el
archivo de 17 que desactivaba dos vistas de búsqueda de ``pos_sale``, porque ``pos_sale`` no está
instalado.

Configuration
=============

Activar las restricciones en el punto de venta
----------------------------------------------

Ir a *Punto de venta › Configuración › Ajustes*, elegir el punto de venta en la parte superior y
buscar, en el bloque **Pago**, la opción **Restricciones por cliente**.

.. figure:: ../static/description/01_activar.png
   :alt: Punto de venta › Configuración › Ajustes › Pago: opción Restricciones por cliente y su lista

   Punto de venta › Configuración › Ajustes › Pago: opción Restricciones por cliente y su lista

- **Restricciones por cliente** (campo ``payment_restrict_enabled`` de ``pos.config``). Opcional;
  desmarcada por defecto. Es el interruptor general: con la casilla desmarcada el POS no filtra
  métodos ni decide la factura, y la lista queda oculta (pero no se borra).
- **Lista de restricciones**: una línea por método de pago restringido. *Agregar una línea* abre el
  formulario de la restricción. El método tiene que estar entre los métodos de pago del punto de
  venta para que aparezca en el POS.

La configuración es **por punto de venta**. Se puede cambiar con la sesión abierta, pero el POS la
lee al cargar: los cambios se ven después de volver a entrar al POS.

Las mismas restricciones, de todos los puntos de venta, se consultan también en *Punto de venta ›
Configuración › Restricciones de pago*. Ahí cada línea indica su punto de venta.

Crear una restricción
---------------------

.. figure:: ../static/description/02_restriccion.png
   :alt: Formulario de la restricción: método, clientes, acciones automáticas y campos del popup

   Formulario de la restricción: método, clientes, acciones automáticas y campos del popup

- **Método de pago**. Obligatorio. El método que queda reservado. No se puede borrar un método de
  pago que tenga restricciones. Para un convenio a crédito conviene un método de tipo *Cuenta de
  cliente*, que no registra entrada de dinero.
- **Clientes autorizados**. Opcional, vacío por defecto. Si queda vacío, el método **no lo ve
  nadie** en ese punto de venta.
- **Crear entrega de inventario**. Opcional; desmarcada por defecto. Si el inventario se actualiza
  al cierre de la sesión, las órdenes de estos clientes generan igual su entrega en el momento de la
  venta, sin importar con qué método se paguen. Si ya se actualiza en tiempo real, no cambia nada.
- **Crear factura**. Opcional; desmarcada por defecto. Decide si las órdenes de estos clientes se
  facturan en el POS. Desmarcada, la orden queda *Pagada* sin factura aunque el POS exija factura, y
  se factura después con la factura agrupada. Marcada, se factura siempre.
- **Crear factura electrónica**. Opcional; desmarcada por defecto. **Hoy no tiene efecto** con
  Jorels 19 (ver *Limitaciones conocidas*).
- **Campos del popup**. Opcional. Cada línea es un dato que el cajero escribe al elegir el método:
  *Etiqueta* (obligatoria, es el texto que ve el cajero), *Tipo* (*Texto corto* por defecto, *Texto
  largo* o *Número entero*) y *Requerido* (desmarcado por defecto). La *Clave* se calcula sola a
  partir de la etiqueta, sin tildes ni espacios (*Habitación* → ``habitacion``). Sin campos, no hay
  popup.

A tener en cuenta:

- Un cliente puede estar en varias restricciones del mismo punto de venta: en ese caso ve todos sus
  métodos autorizados.
- El popup sale para cualquier método que tenga campos, **aunque la casilla general esté
  desmarcada**.
- Si las etiquetas son *Huésped* y *Habitación*, sus valores se copian además a los campos
  ``hotel_guest`` y ``hotel_room`` de la orden (también sirven las claves ``huesped``, ``guest``,
  ``nombre_huesped``, ``room`` y ``numero_habitacion``).

Usage
=====

Métodos de pago según el cliente
--------------------------------

En la pantalla de pago, la lista de métodos se recalcula cada vez que cambia el cliente. Con un
cliente sin restricción, o sin cliente, los métodos restringidos no aparecen:

.. figure:: ../static/description/03_pago_sin_restriccion.png
   :alt: Pantalla de pago con un cliente sin restricción: faltan los métodos restringidos

   Pantalla de pago con un cliente sin restricción: faltan los métodos restringidos

Al elegir un cliente autorizado quedan solo sus métodos, y la casilla **Recibo/Factura** toma el
valor de *Crear factura* de la restricción:

.. figure:: ../static/description/04_pago_con_restriccion.png
   :alt: Pantalla de pago con un cliente del convenio: solo su método y sin factura

   Pantalla de pago con un cliente del convenio: solo su método y sin factura

Popup de datos adicionales
--------------------------

Si el método tiene campos configurados, al pulsarlo aparece el popup. Los campos marcados con * son
obligatorios: *Confirmar* no avanza mientras estén vacíos. *Cancelar*, la X o la tecla Esc cierran
el popup sin agregar el pago.

.. figure:: ../static/description/05_popup_datos.png
   :alt: Popup con los datos del huésped antes de agregar el pago

   Popup con los datos del huésped antes de agregar el pago

Al confirmar, el POS busca órdenes de **hoy** con la misma restricción y algún valor igual (sin
distinguir mayúsculas). Si encuentra alguna, muestra el aviso con el número y la hora de cada
orden. **Registrar igualmente** sigue con el pago; **Cancelar** lo descarta. El aviso no bloquea:
puede haber dos huéspedes en la misma habitación.

.. figure:: ../static/description/06_aviso_duplicado.png
   :alt: Aviso de posible registro duplicado

   Aviso de posible registro duplicado

Los datos quedan guardados en la orden, en la pestaña **Datos de restricción** del formulario de la
orden en el backend:

.. figure:: ../static/description/08_orden_datos.png
   :alt: Formulario de la orden: pestaña Datos de restricción con los datos del popup

   Formulario de la orden: pestaña Datos de restricción con los datos del popup

Factura según la restricción
----------------------------

Al sincronizar la orden, el servidor vuelve a aplicar *Crear factura* de la restricción del
cliente, aunque otro módulo del POS haya vuelto a marcar *Recibo/Factura* (por ejemplo la
facturación obligatoria). Si el cliente está en varias restricciones, manda la del método con que
se pagó. Hay dos excepciones: una orden que ya tiene factura no se toca, y la devolución de una
orden facturada sigue facturada (lleva nota crédito).

Esto solo ocurre si el punto de venta tiene activa la casilla *Restricciones por cliente*. Los
clientes sin restricción conservan lo que envió el POS.

Factura agrupada
----------------

En *Punto de venta › Órdenes › Órdenes*, seleccionar las órdenes y usar **Acciones › Crear factura
agrupada** (no el botón *Crear facturas* del estándar).

.. figure:: ../static/description/07_factura_agrupada.png
   :alt: Lista de órdenes: selección y acción Crear factura agrupada

   Lista de órdenes: selección y acción Crear factura agrupada

- Solo toma órdenes en estado *Pagado*, sin factura y con cliente. Las demás se ignoran; si no queda
  ninguna, muestra un error.
- Crea **una factura por cliente**, con las líneas de todas sus órdenes, y la publica. La
  referencia y el origen de la factura listan los números de las órdenes.
- Usa el **diario de facturas del punto de venta** de la primera orden del grupo.
- Concilia los pagos de las órdenes con la factura, como el estándar. Las órdenes pasan a
  *Registrado* con la factura enlazada, y ya no se pueden volver a agrupar.
- Al terminar abre la lista de facturas creadas.

Si la factura sale electrónica depende de Jorels 19 y del diario (ver *Limitaciones conocidas*).
Verificar en STG.

Informes de convenios
---------------------

El menú *Punto de venta › Reportes › Convenios y restricciones* (solo administradores del POS)
tiene tres informes de órdenes con restricción:

- **Órdenes del día**: lista con fecha, cliente, restricción, datos del popup, total, estado y
  factura. Se puede agrupar por restricción, cliente, fecha, mes o estado.
- **Reporte mensual**: la misma lista, agrupada por día.
- **Consumo de productos**: las líneas de esas órdenes, agrupadas por producto.

.. figure:: ../static/description/09_informe_convenios.png
   :alt: Reportes › Convenios y restricciones › Órdenes del día

   Reportes › Convenios y restricciones › Órdenes del día

Hoy *Reporte mensual* y *Consumo de productos* dan error al abrirse (ver *Limitaciones conocidas*).

Solución de problemas
---------------------

- **El cliente ve todos los métodos, o un método restringido no desaparece.** Revisar que la
  casilla *Restricciones por cliente* esté marcada en ese punto de venta y volver a entrar al POS:
  los cambios de configuración no llegan a una sesión ya cargada.
- **Un método no aparece para nadie.** Su restricción tiene la lista de clientes vacía.
- **El popup no aparece.** La restricción de ese método no tiene campos, o el POS no se recargó
  después de agregarlos.
- **La orden se facturó y debía quedar para la factura agrupada.** Revisar que *Crear factura* esté
  desmarcada en la restricción, que el cliente de la orden sea el autorizado y que la casilla general
  esté activa.
- **"No hay órdenes válidas para facturar".** Las órdenes seleccionadas ya tienen factura, no están
  pagadas o no tienen cliente.
- **Al abrir *Reporte mensual* o *Consumo de productos* sale "Ocurrió un error".** Es la limitación
  de los filtros de fecha. Usar *Órdenes del día*, quitar el filtro *Hoy* y agrupar por mes.

Known issues / Roadmap
======================

Limitaciones conocidas
----------------------

- **Pendiente de decisión: *Crear factura electrónica* no tiene efecto.** En Odoo 17 la casilla
  elegía entre factura normal y electrónica mediante ``to_electronic_invoice`` de Jorels. Jorels 19
  eliminó ese campo, y el POS solo lo marca si existe, así que hoy la casilla no hace nada. Se
  propuso reemplazarla por un diario opcional en cada restricción, con script de datos. Falta que lo
  confirme el líder técnico. Verificar en STG, donde la usan las restricciones que facturan con un
  diario electrónico propio.
- **Pendiente de configuración: la factura agrupada sale electrónica solo si el diario de facturas
  del POS tiene resolución DIAN.** Con Jorels 19 ya no hay un diario electrónico aparte en el punto
  de venta: la factura agrupada usa el diario de facturas del POS, y es electrónica si ese diario lo
  es. Verificar en STG antes de producción.
- **Los filtros *Esta semana* y *Este mes* de los informes dan error**, y por eso *Reporte mensual* y
  *Consumo de productos*, que abren con *Este mes*, muestran "Ocurrió un error" al entrar. Sus
  dominios usan ``context_today().replace(day=1)`` y ``context_today().weekday()``, que el evaluador de
  dominios del navegador no soporta. En el Odoo 17 de referencia los dominios son los mismos y ese
  evaluador tampoco tiene esos métodos, así que el error viene de antes de la migración.
- **Horas y "hoy" en UTC.** El aviso de duplicado compara con la fecha del servidor y muestra la
  hora en UTC: una orden de las 2:02 p. m. en Colombia sale como 19:02. El filtro *Hoy* de los
  informes arma el rango sin convertir de zona horaria, así que probablemente también corta el día
  a las 7:00 p. m. hora de Colombia. Esto último no se comprobó con órdenes reales de la noche.
- **La restricción se muestra como ``pos.payment.customer.restriction,3``** en la orden y en los
  informes, porque el modelo no tiene un campo de nombre. Pasa igual en 17.
- La lista de restricciones en *Ajustes* es angosta y corta los encabezados. Para ver todas las
  columnas conviene el menú *Configuración › Restricciones de pago*.
- Los campos ``is_hotel_order``, ``hotel_guest``, ``hotel_room`` y ``hotel_data_summary`` de la orden se
  calculan y guardan, pero ninguna vista los muestra.
- El requerimiento de negocio (``REQUERIMIENTO IT DESAYUNOS HOTELES.md``) pide también precios de
  convenio, combo desayuno y bebida, el descuento del 10 % para huéspedes y anulaciones con
  autorización. Este módulo no implementa esas partes.
- Falta ``static/description/icon.png``: en *Aplicaciones* se ve el ícono genérico de Odoo.

Componentes
-----------

- ``models/pos_payment_customer_restriction.py`` y ``models/pos_payment_restriction_field.py``: la
  restricción (punto de venta, método, clientes, casillas) y los campos del popup, con la clave
  calculada desde la etiqueta.
- ``models/pos_config.py``: los campos del punto de venta y ``_load_pos_data_read``, que agrega al
  POS un diccionario plano de restricciones por método en ``config._payment_restrictions``.
- ``models/res_config_settings.py``: los campos relacionados de *Ajustes*. Su ``create`` escribe las
  restricciones directo en ``pos.config``, porque *Ajustes* puede descartar cambios en los campos del
  popup cuando los IDs de las restricciones no cambian.
- ``models/pos_order.py``: datos del popup (``restriction_data``, ``restriction_id`` y campos derivados),
  búsqueda de duplicados, entrega en tiempo real, la decisión de ``to_invoice`` en
  ``_process_saved_order`` y la factura agrupada.
- ``static/src/js/payment_method_restrict.js``: parches de ``PaymentScreen`` (filtro de métodos,
  popup, duplicados), de ``PosStore.selectPartner`` (vuelve a aplicar la factura al cambiar el
  cliente) y de ``PosOrder.serializeForORM`` (envía ``restriction_id``, que el POS descartaría porque su
  modelo no está cargado en el POS).
- ``static/src/js/payment_restriction_popup.js`` y ``.xml``: el popup, un componente sobre ``Dialog`` que
  se abre con ``makeAwaitable``.
- ``views/pos_config_views.xml``: el bloque de *Ajustes*, las vistas de la restricción y el menú de
  configuración. ``views/pos_hotel_report_views.xml``: la pestaña de la orden y los informes.
- ``data/pos_order_server_actions.xml``: la acción *Crear factura agrupada*.

Notas para mantenimiento
------------------------

- **Tests.** ``tests/test_restriction_invoice.py`` cubre la decisión de ``to_invoice`` en el servidor
  (la restricción manda sobre lo que envía el POS, en los dos sentidos; clientes sin restricción y
  casilla general apagada no se tocan) y la factura agrupada (una sola factura con el diario del
  POS, órdenes en *Registrado*, sin refacturar). El filtro de métodos, el popup y el aviso de
  duplicado no tienen test automático: se prueban a mano en el navegador.
- **Motor propio de agrupación.** No usa ``_prepare_invoice_vals`` del estándar sobre todo el grupo
  porque en 19 exige un solo punto de venta, usuario y posición fiscal, y partiría la factura de un
  hotel por cajero. Lo llama sobre la primera orden del grupo: diario, posición fiscal y plazo de
  pago salen de esa orden. La fecha de la factura es la de esa orden si su sesión sigue abierta, y
  la del día si está cerrada.
- **Dos lecturas de la restricción.** Si un cliente está en varias restricciones, el POS aplica la
  primera que encuentra y el servidor la del método de pago usado. El resultado final lo decide el
  servidor.
- **Interacción con la facturación obligatoria.** La restricción debe seguir prevaleciendo en el
  servidor. Si otro módulo fuerza ``to_invoice`` en Python después de ``_process_saved_order``, la
  factura agrupada deja de funcionar. Revisar en particular la versión 19 del módulo de fidelización
  de Jorels que usa STG.

Credits
=======

Authors
-------

- Libertario Coffee

Contributors
------------

- Libertario Coffee
- Cristian Mira (migración a Odoo 19)
