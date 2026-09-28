==================
POS API Credibanco
==================

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

Cobra con el **datáfono Credibanco** desde la pantalla de pago del Punto de Venta. El cajero agrega
el método de pago Credibanco, revisa el monto y pulsa **Enviar a Datafono**: el POS arma la trama
del protocolo Credibanco (total, IVA, IAC, propina, caja, número de transacción y cajero), la envía
al datáfono y, si el cliente aprueba, deja la línea pagada con el monto que realmente cobró el
terminal y su número de aprobación.

El navegador de la caja no habla con el datáfono directamente: lo hace a través de un **servicio
puente WebSocket** que corre en el equipo de la caja (contenedor ``websocket-api-credibanco``), y ese
puente habla por TCP/IP con el datáfono.

Además del cobro, el módulo cubre lo que pasa cuando algo sale mal:

- **Venta sin respuesta**: si el datáfono no contesta o devuelve "sin respuesta final", la venta
  queda marcada como pendiente y el POS obliga a **recuperarla** antes de cobrar de nuevo, para no
  cobrar dos veces.
- **Anulación**: un pago aprobado se puede anular desde la misma pantalla de pago; la anulación se
  registra como una **línea de pago negativa**, igual que en Odoo 17.
- **Trazabilidad**: cada pago guarda la respuesta completa del datáfono y la muestra en la ficha
  del pago como un desglose legible (franquicia, recibo, terminal, cuotas...).

Se integra con el marco de terminales de pago del núcleo de Odoo 19
(``use_payment_terminal = 'credibanco'``), que es el que evita dos pagos electrónicos a la vez y
maneja los estados de la línea.

**Table of contents**

.. contents::
   :local:

Installation
============

Dependencias
------------

- ``point_of_sale`` (Odoo Community). No hay dependencias de Python adicionales.
- ``pos_voucher_num`` es **opcional**: si está instalado, el número de aprobación se copia también a
  su campo ``voucher_num``. En Odoo 17 era una dependencia obligatoria; en 19 la integración es por
  valor y este módulo se instala sin él.
- **Servicio puente WebSocket** ``websocket-api-credibanco`` (imagen Docker
  ``soportedevlibertario/api_credibanco``), instalado en el equipo de cada caja. Expone el WebSocket
  en el puerto ``8080`` (ruta ``/ws``) y escucha al datáfono en el puerto TCP ``8013``. Su código y su
  guía de instalación están en ``api_credibanco-main/`` dentro de este módulo; Odoo no lo instala ni
  lo arranca.
- **Datáfono Credibanco** en la misma red que la caja, configurado desde su menú técnico con la IP y
  el puerto del equipo de la caja. La integración se desarrolló con un Ingenico Lane/3000.

Pasos de instalación
--------------------

- En el equipo de la caja: instalar Docker y levantar el puente con el ``stack.yml`` de
  ``api_credibanco-main/`` (ver su ``README.md``). En ``resource/tcpIp.ini`` del puente se asocia la IP de
  cada datáfono con el **nombre de terminal** (por ejemplo ``dataf001``) que luego se configura en
  Odoo.
- En Odoo: instalar el módulo desde *Aplicaciones*. Crea el modelo del desglose
  (``pos.payment.credibanco``), el asistente de carga manual, los campos de ``pos.payment`` y
  ``pos.payment.method``, y el menú *Credibanco Settings*.
- Configurar el método de pago (ver *Configuración*) y **volver a entrar al POS** desde el backend
  para que cargue los archivos y los datos nuevos.

Migración desde Odoo 17
-----------------------

- En 17 la terminal se activaba con la casilla ``enable_pos_credibanco`` del método de pago. El script
  ``migrations/19.0.1.0.0/pre-migration.py`` pasa esos métodos a ``use_payment_terminal = 'credibanco'``
  e ``Integración = Terminal``. Solo toca los métodos que tenían la casilla marcada y que no tenían
  otra terminal asignada, así que se puede ejecutar más de una vez. Si la columna vieja no existe
  (instalación nueva), no hace nada.
- Nombre, host y puerto del datáfono conservan el mismo nombre técnico que en 17
  (``pos_payment_terminal_name``, ``pos_ip_host``, ``pos_websocket_port``) y no necesitan script. El script
  **no rellena** los valores que en 17 se asumían cuando estaban vacíos (``dataf001``, ``localhost``,
  ``8080``): un método migrado sin esos datos no se puede guardar hasta completarlos.
- **Número de voucher**: el código de 19 escribe en ``voucher_num`` (en 17 el campo se llamaba
  ``vaucher_num``). El renombre de la columna y de los datos lo hace ``pos_voucher_num`` en su
  migración ``19.0.1.1.0``; este módulo no migra datos de voucher.
- Los ajustes de *Payment Terminals* de 17 (``module_pos_credibanco`` en Ajustes) no se portaron.

Configuration
=============

Ir a *Punto de venta › Configuración › Credibanco Settings* (solo lo ven los responsables del POS).
La lista muestra **todos** los métodos de pago con su terminal, nombre, host y puerto; no permite
crear ni borrar. Abrir el método que va a cobrar con el datáfono.

.. figure:: ../static/description/01_credibanco_settings.png
   :alt: Punto de venta › Configuración › Credibanco Settings: lista de métodos y su terminal

   Punto de venta › Configuración › Credibanco Settings: lista de métodos y su terminal

En el formulario del método de pago (es el mismo de *Configuración › Métodos de pago*):

.. figure:: ../static/description/02_metodo_pago.png
   :alt: Método de pago: integración con Credibanco y bloque Datáfono Credibanco

   Método de pago: integración con Credibanco y bloque Datáfono Credibanco

- **Integración** = *Terminal* y luego **Integrar con** = *Credibanco*. Obligatorios. *Integrar
  con* solo aparece con la integración en *Terminal* y un diario que no sea de efectivo. Al elegir
  Credibanco aparece el bloque **Datáfono Credibanco**.
- **Nombre de la terminal** (``pos_payment_terminal_name``). Obligatorio, sin valor por defecto. Es
  el prefijo que lleva cada trama y debe coincidir con el nombre que el puente asocia a la IP del
  datáfono en ``tcpIp.ini`` (por ejemplo ``dataf001``).
- **Host del datáfono** (``pos_ip_host``). Obligatorio, sin valor por defecto. Pese al nombre, es la
  IP o el nombre del **equipo donde corre el puente**, tal como lo ve el navegador de la caja: el
  navegador se conecta directo a ``ws://<host>:<puerto>/ws`` (o ``wss://`` si el POS se abre por https).
- **Puerto** (``pos_websocket_port``). Obligatorio; ``8080`` por defecto, que es el puerto del puente.
- **Espera de respuesta (s)** (``credibanco_timeout``). Opcional; ``100`` por defecto en métodos
  nuevos. Pasado ese tiempo sin respuesta, la venta queda pendiente de recuperar. Debe ser mayor
  que los 90 s que espera el propio puente (``LONG_TIMEOUT`` en ``tef.ini``), para que el primero en
  rendirse sea el datáfono y el cajero vea su error.
- **Diario**: uno de banco. Un método de efectivo no puede ser terminal Credibanco.
- **Punto de venta**: agregar el método a los puntos de venta que lo usan.

Lo que **no** se configura:

- **Número de caja** (posición 42 de la trama). Se compone al cobrar como *id de la sesión* + *id
  del cajero*, sin separador, igual que en la integración certificada de Odoo 17. Si supera los 10
  caracteres del protocolo, el cobro se rechaza con un mensaje; nunca se recorta.
- **Números de transacción** (posición 53). Salen de una secuencia por método de pago
  (``pos_api_credibanco.trx.<id>``) que se crea sola al primer cobro. El POS reserva bloques de 25
  para poder seguir cobrando si pierde el servidor.
- **Impuestos**. El servidor clasifica los impuestos de venta por el nombre de su **grupo**: los que
  empiezan por ``IVA`` van a la posición 41 y los que empiezan por ``INC`` (el "IAC" del datáfono) a la
  82. Las retenciones y los impuestos negativos no viajan. Si el pedido tiene impuestos pero
  ninguno es IVA ni INC, el cobro se rechaza con el nombre de los grupos encontrados.
- **Propina**. Se toma del producto de propina del punto de venta (*Ajustes › Propinas*).

Los cambios se ven en el POS después de volver a entrar a la sesión.

Usage
=====

Cobro con el datáfono
---------------------

En la pantalla de pago, tocar el método Credibanco. Se crea una línea por el saldo pendiente con el
estado *Solicitud de pago pendiente*. **Agregar la línea no envía nada**: el monto se puede ajustar
con el teclado (pago parcial) antes de enviar.

.. figure:: ../static/description/03_pantalla_pago.png
   :alt: Pantalla de pago con la línea Credibanco lista para enviar

   Pantalla de pago con la línea Credibanco lista para enviar

Al pulsar **Enviar a Datafono**:

- El POS calcula los valores y abre **Valores de la transacción** con TOTAL, IVA, IAC y PROPINA.
  *Cancelar* no envía nada; *Continuar* envía la venta al datáfono.
- El cliente pasa la tarjeta y aprueba en el datáfono. Mientras tanto la línea muestra *Solicitud
  enviada*.
- Si el datáfono aprueba, la línea queda pagada con el **monto que cobró el terminal** (valor total
  más la propina que devuelve en la posición 80), el número de aprobación y el identificador de la
  transacción. En el recibo sale *Aprob.:* seguido del número de aprobación. Si con eso el pedido queda pagado y el punto de
  venta tiene activo *Validar órdenes de forma automática* (opción estándar de *Ajustes*, activa por defecto), el
  pedido se valida solo.
- Si el datáfono rechaza, se muestra el motivo según su código (02 rechazada, 05 problema de
  comunicación, 06 error de trama, 09 a 12 errores de formato, 13 tiempo agotado, 99 puerto
  ocupado). La línea queda en *Transacción cancelada* y se puede volver a enviar.

**Propina**: si el pedido tiene propina (producto de propina del POS) y la línea cubre el pedido
entero, el TOTAL se envía sin la propina y la propina viaja aparte en la posición 81.

Venta sin respuesta y recuperación
----------------------------------

Si el datáfono no contesta dentro de la espera configurada, se corta la conexión o responde con el
código 03 (sin respuesta final), la venta **puede haber quedado aprobada** en el terminal. Por eso:

- El POS guarda en la línea la venta enviada. Sin respuesta, avisa *Sin respuesta del datáfono*;
  con el código 03 abre directamente el diálogo **Recuperar** (en el datáfono: TECLA 3 y luego
  TECLA 9). *Más tarde* deja la venta pendiente.
- El botón de la línea cambia a **Recuperar venta**: pulsarlo consulta la venta pendiente, **nunca
  envía una venta nueva**.
- Si la página se recarga, al volver a la pantalla de pago se ofrece recuperar la venta pendiente.
- No se puede **validar** el pedido mientras haya una venta pendiente.
- Borrar esa línea pide confirmar que en el datáfono se verificó que la venta **no** fue aprobada.
- Después de tres intentos sin respuesta final, el POS pide consultar el datáfono y avisar a un
  responsable antes de cobrar de nuevo.

El botón estándar *Forzar terminación* sigue visible en algunos estados, pero con Credibanco no marca el
pago: muestra *No se puede forzar el pago* y pide usar la recuperación.

Cancelar una venta en curso
---------------------------

Quitar la línea (×) mientras la venta está enviada manda al datáfono una **anulación** con los
datos de esa venta. Si el datáfono no la confirma, la línea sigue pendiente y el aviso pide usar
*Recuperar* antes de continuar.

Anular un pago aprobado
-----------------------

Mientras el pedido sigue en la pantalla de pago, una línea Credibanco aprobada muestra el botón
estándar **Revertir**. Con Credibanco no deja la línea en cero: si el datáfono aprueba la anulación,
se agrega una **línea negativa** por el mismo monto (con propina incluida) y la línea original
queda como estaba, ya sin botón de revertir. El pedido vuelve a quedar con saldo pendiente: hay que
cobrarlo de otra forma o cancelarlo.

La línea de anulación **no se puede borrar**: ya existe una devolución en el datáfono y borrarla
dejaría la venta pagada en Odoo.

Información del pago en el backend
----------------------------------

En *Punto de venta › Órdenes › Pagos*, la ficha de un pago Credibanco muestra el **número de
aprobación** y el desglose de la respuesta del datáfono. Un responsable del POS puede agregar un
concepto a mano con **Agregar información**.

.. figure:: ../static/description/04_informacion_pago.png
   :alt: Ficha del pago: número de aprobación y desglose de la respuesta del datáfono

   Ficha del pago: número de aprobación y desglose de la respuesta del datáfono

Solución de problemas
---------------------

- **"Sin respuesta del datáfono" en todos los cobros.** El navegador no llega al puente. Revisar
  que el contenedor ``websocket-api-credibanco`` esté corriendo en la caja y que *Host del datáfono* y
  *Puerto* apunten a ese equipo. Si el POS se abre por **https**, el navegador usa ``wss://`` y el
  puente no tiene TLS: la conexión falla siempre (ver *Limitaciones*).
- **"Error en la trama" o "Campo no corresponde".** La respuesta no se pudo leer o un valor no
  cumple el formato del datáfono. Revisar que el *Nombre de la terminal* coincida con ``tcpIp.ini`` y
  avisar a IT.
- **"El número de caja excede el protocolo".** La sesión y el cajero forman un número de más de 10
  caracteres. No se puede cobrar con el datáfono en esa sesión; avisar a IT.
- **"Impuestos no reconocidos".** Algún producto tiene impuestos de un grupo que no empieza por
  ``IVA`` ni ``INC``. Corregir el grupo del impuesto en contabilidad.
- **"Sin números de transacción disponibles".** Se agotó el bloque reservado y no hay conexión con
  el servidor. Esperar a recuperar la conexión; no se repiten números.
- **"Falta el cajero"** o **"Sesión no disponible".** Iniciar sesión con un empleado o recargar el
  POS.
- **El método no aparece en el POS o no abre el datáfono.** Verificar que el método esté asignado
  al punto de venta, con *Integrar con = Credibanco*, y volver a entrar a la sesión.

Known issues / Roadmap
======================

Limitaciones conocidas
----------------------

- **Validación con el datáfono real pendiente.** La base local tiene ventas aprobadas por un
  datáfono (respuestas completas con franquicia, recibo y terminal), pero la anulación, la
  recuperación y el cobro con propina no están validados de punta a punta con el terminal. Hay que
  probarlos en cada tienda antes de habilitar el método.
- **Propina cobrada.** El monto de la línea aprobada es la posición 40 (valor total) más la 80
  (propina). Si el 40 del datáfono ya incluye la propina, se contaría dos veces. En 17 se sumaban
  el 40 y el 81, que la respuesta de compra no trae. Confirmar con una compra real con propina.
- **POS por https.** Con https el navegador usa ``wss://``, y el puente actual no tiene TLS: ningún
  cobro conecta. En 17 la URL era siempre ``ws://``. Hoy el POS tiene que abrirse por http en la red
  local, o el puente necesita TLS.
- **Anular solo antes de validar.** El botón *Revertir* existe solo en la pantalla de pago y se
  pierde al enviar otra línea electrónica. Con *Validar órdenes de forma automática* activo, un pago
  que cubre todo el pedido lo valida enseguida y ya no se puede anular desde el POS. Los pedidos de
  reembolso tampoco pasan por el datáfono: el monto negativo se rechaza ("El monto a pagar debe ser
  mayor que 0").
- **Desglose solo al crear el pago.** La respuesta se convierte en desglose y en voucher en el
  ``create`` de ``pos.payment``. Si el pago ya estaba sincronizado (pedido de restaurante guardado antes
  de pagar) y llega como ``write``, se guarda la respuesta cruda pero no el desglose ni el voucher.
- **Respuestas compartidas.** El puente reenvía cada respuesta a todas las conexiones abiertas. El
  POS solo acepta una respuesta de venta si trae su caja (42) y su número de transacción (53), y una
  anulación de un pago aprobado si trae su recibo (43). Las respuestas de recuperación y de
  anulación de una venta en curso no traen esos datos y se aceptan tal cual: dos cajas sobre el
  mismo puente podrían cruzarlas.
- **Puente sin autenticación** en la red local, y escribe en su salida estándar lo que recibe y lo
  que responde el datáfono (incluidos datos de la tarjeta).
- **Impuestos mixtos.** Si el pedido tiene al menos un impuesto IVA o INC, los impuestos de otros
  grupos no se informan y el cobro sigue sin aviso.
- **Cajero (83).** Viaja el primer nombre del cajero, recortado a 12 caracteres. Falta confirmar
  qué espera el banco para la conciliación.
- Los códigos de error de E/S del puente (``MSG_CODE_1``, ``MSG_CODE_2``) no están mapeados porque no
  se confirmó su código en la respuesta: salen con el mensaje genérico de rechazo.
- **Interfaz.** La lista *Credibanco Settings* muestra todos los métodos de pago sin filtrar, con
  títulos en inglés (*Payment terminal name*, *Ip host POS*) y la acción se llama *Credibanco
  Terminals*. En el formulario, el texto sobre el número de caja ocupa la columna de etiquetas y
  deja *Espera de respuesta (s)* desalineado (ver captura). Los mensajes del POS están en español en
  el código, sin traducción.

Componentes
-----------

- ``models/pos_payment_methods.py``: terminal ``credibanco`` en la selección del núcleo, campos del
  datáfono, validaciones, carga al POS (``_load_pos_data_fields``), mapa de impuestos por grupo
  (``get_credibanco_tax_map``) y reserva de números de transacción
  (``reserve_credibanco_transaction_numbers``).
- ``models/pos_payment.py``: campos ``credibanco_*`` del pago (aprobación, respuesta, venta pendiente,
  valores enviados en 42/53/83, marca de anulación) y el ``create`` que genera el desglose.
- ``models/pos_payment_credibanco.py`` y ``static/data/fields_credibanco.json``: filas del desglose y
  etiquetas de cada posición de la respuesta.
- ``wizard/``: *Agregar información*, solo para responsables del POS.
- ``views/``: menú *Credibanco Settings*, bloque del método de pago y bloque de la ficha del pago.
- ``static/src/app/utils/payment/credibanco_protocol.js``: trama, LRC, límites por campo, lectura de
  respuestas y mensajes por código. Sin dependencias de Odoo.
- ``static/src/app/utils/payment/credibanco_transport.js``: WebSocket con espera, una petición a la
  vez y correlación de respuestas.
- ``static/src/app/utils/payment/credibanco_terminal.js``: la terminal (``PaymentInterface``)
  registrada como ``credibanco``: venta, cancelación, anulación con línea negativa y recuperación.
- ``static/src/app/screens/payment_screen/``: recuperación al abrir la pantalla, bloqueos de borrado
  y de validación, bloqueo de *Forzar terminación* y texto del botón (*Enviar a Datafono* /
  *Recuperar venta*).
- ``static/src/app/components/popups/text_list_popup/``: diálogo *Valores de la transacción*.
- ``migrations/19.0.1.0.0/pre-migration.py``: ``enable_pos_credibanco`` → ``use_payment_terminal``.
- ``api_credibanco-main/``: código, recursos (``tcpIp.ini``, ``tef.ini``, ``fields.ini``,
  ``functionsFields.ini``) y guía de instalación del puente. Odoo no lo carga.
- ``tools/credibanco_fake_terminal.py``: simulador de datáfono para desarrollo
  (``--outcome approved|rejected|no-answer|recover-then|bad-lrc``, ``--selftest``). Odoo no lo carga.
- ``doc/historial_17/``: notas de la migración 16 → 17 (se conservan como historial).

Notas para mantenimiento
------------------------

- **La trama es la certificada.** El número de caja (42 = sesión + cajero), el orden de los campos
  y el LRC reproducen lo que enviaba Odoo 17. No se rellenan ni se recortan valores: el puente
  rellena cada campo a su longitud (``fields.ini``) y un valor que no cabe se rechaza con mensaje.
- **``sendPaymentReversal`` devuelve ``false`` a propósito** aunque la anulación se apruebe. Con ``true``
  el núcleo dejaría la línea en 0 con estado *reversed*, y al cierre no habría asiento que
  conciliar. Con ``false`` queda el ``+X`` original y la línea ``-X`` de la anulación.
- **Anulación y recuperación repiten lo enviado.** Leen 42/53/83 de los campos guardados en el
  pago, no los recalculan desde la sesión.
- **``canForceDone``** (en ``payment_lines.js``) no lo llama ninguna plantilla del núcleo 19: el
  bloqueo real de *Forzar terminación* es el parche de ``sendForceDone`` en ``payment_screen.js``.
- **``fastPayments`` es ``false``**: el núcleo no envía la venta al agregar la línea, para dejar
  ajustar un pago parcial.
- **Overrides a vigilar** en cada actualización del núcleo: ``PaymentScreen.deletePaymentLine``,
  ``sendForceDone``, ``OrderPaymentValidation.askBeforeValidation`` y la plantilla
  ``point_of_sale.PaymentScreenPaymentLines`` (se reemplazan los botones de los estados ``pending`` y
  ``retry``).
- **Tests.** ``tests/test_pos_payment_method.py`` tiene 33 pruebas de configuración, persistencia,
  secuencias, anulación y mapa de impuestos. El JS del POS no tiene test automático: se valida a
  mano en el navegador o con el simulador.

Credits
=======

Authors
-------

- Libertario Coffee Roasters

Contributors
------------

- Libertario Coffee Roasters
- danilosantoslibertario (desarrollo original en Odoo 16/17)
