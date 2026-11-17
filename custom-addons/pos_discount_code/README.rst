=================
POS Discount Code
=================

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

Agrega al Punto de Venta el botón **Convenio To Plus** para canjear bonos (códigos promocionales,
cupones y tarjetas de regalo) pidiendo el **tipo y el número de documento** de quien canjea, y deja
el canje **registrado en la orden** para poder rastrearlo después.

El módulo no crea descuentos propios: aplica los programas de *Punto de venta › Productos ›
Descuentos y lealtad* con la lealtad nativa de Odoo (``pos_loyalty``). En las cajas donde está
activo, el botón reemplaza al «Enter Code» de Odoo.

- Formulario con tipo de documento, número y código, validado desde el primer **Validar**:
  - promociones con código: vigencia y lista de precios, en la caja;
  - cupones y tarjetas de regalo: consulta al servidor que **no gasta** el cupón;
  - en los tipos numéricos (NIT, CC, TI, TE, CE, NIUP), el número solo admite dígitos.
- El cupón se gasta recién al cobrar.
- Vista previa antes de aplicar: programa, valor (%, fijo o saldo de la tarjeta), vigencia y
  documento.
- Un código no se aplica dos veces en la misma orden. Si el cajero quitó la línea del descuento,
  el código se puede volver a aplicar sin que el cliente pierda el bono.
- Si la orden ya tenía otro código, se avisa en la vista previa y queda solo el nuevo.
- Pestaña **Descuento** en la orden con el programa, el código, el valor descontado, el estado
  del bono al canjear y el documento. El valor y el estado los calcula el servidor.
- Antes de abrir el formulario se revisa que ``pos_loyalty`` tenga la forma esperada: si una
  actualización de Odoo la cambia, el botón muestra un aviso en vez de aplicar descuentos a medias.

**Table of contents**

.. contents::
   :local:

Configuration
=============

**Botón por caja.** En *Punto de Venta › Configuración › Ajustes*, elegir la caja en el selector
superior y, en el bloque de precios y descuentos, marcar **Botón de descuento (Convenio To Plus)**.
Viene marcado por defecto. Desmarcado, esa caja vuelve a mostrar el «Enter Code» de Odoo.

.. figure:: ../static/description/01_configuracion.png
   :alt: Punto de Venta › Configuración › Ajustes: elegir la caja y marcar «Botón de descuento (Convenio To Plus)»

   Punto de Venta › Configuración › Ajustes: elegir la caja y marcar «Botón de descuento (Convenio To Plus)»

El botón aparece solo si la caja tiene cargado al menos un programa canjeable con código.

**Programas de descuento.** En *Punto de Venta › Productos › Descuentos y lealtad*, crear el
programa con *Disponible en: Punto de venta*. Sirven los tipos **Código de descuento**,
**Cupones**, **Promociones** (con regla de código), **Tarjeta de regalo** y **Cupones para la
próxima orden**; las tarjetas de lealtad por puntos no se canjean con este botón.

.. figure:: ../static/description/02_programa.png
   :alt: Programa de tipo «Código de descuento» con la regla del código y la compra mínima

   Programa de tipo «Código de descuento» con la regla del código y la compra mínima

- Un descuento fijo nunca supera el total de la orden. Si el bono no debe usarse en compras
  menores a su valor, configurar una **compra mínima** en la regla del código.
- Un código promocional no guarda saldo; para eso se usa una tarjeta de regalo.
- Los cambios en los programas llegan a la caja la próxima vez que se carga el POS.

Usage
=====

Con los productos ya en la orden, abrir las acciones (**⋮**) y pulsar **Convenio To Plus**:

.. figure:: ../static/description/03_boton.png
   :alt: Acciones de la orden: botón «Convenio To Plus»

   Acciones de la orden: botón «Convenio To Plus»

Elegir el tipo de documento, escribir el número y el código, y pulsar **Validar**. Los errores
(número vacío o con puntos, código inexistente, vencido o ya aplicado) se muestran en el mismo
formulario:

.. figure:: ../static/description/04_formulario.png
   :alt: Formulario del canje con tipo de documento, número y código

   Formulario del canje con tipo de documento, número y código

La vista previa muestra el bono y el documento. **Modificar** vuelve al formulario y **Aplicar**
activa el código en la orden:

.. figure:: ../static/description/05_vista_previa.png
   :alt: Vista previa antes de aplicar el bono

   Vista previa antes de aplicar el bono

El descuento queda como una línea más de la orden y un aviso muestra el valor descontado:

.. figure:: ../static/description/06_descuento_aplicado.png
   :alt: Orden con la línea del descuento y el aviso del valor aplicado

   Orden con la línea del descuento y el aviso del valor aplicado

Si la orden todavía no cumple las condiciones del bono (por ejemplo, la compra mínima), el código
queda activado con el aviso «el descuento se aplicará cuando la orden cumpla las condiciones del
bono». La línea aparece sola cuando se cumplan, también si la orden se envió antes a cocina.

Se cobra normalmente. Al sincronizar la orden pagada, el servidor registra el canje en la pestaña
**Descuento** de la orden:

.. figure:: ../static/description/07_registro_orden.png
   :alt: Pestaña «Descuento» de una orden pagada

   Pestaña «Descuento» de una orden pagada

Qué se guarda en la orden
-------------------------

- **Nombre del descuento** y **programa**: los del programa, no lo que envía la caja.
- **Código de descuento**: el digitado en la caja.
- **Valor del descuento**: suma de las líneas de descuento del programa, con impuestos. Se
  recalcula si cambian las líneas.
- **Fecha de vigencia**: la fecha final del programa.
- **Estado al canjear**: vigente o vencido **en la fecha del canje**, según el día local del
  cajero. No cambia aunque el programa venza después.
- **Tipo y número de documento**: los digitados; en los tipos numéricos se quitan espacios, puntos
  y guiones.
- **Fecha de canje**: el momento en que se aplicó el código.

Reglas del servidor
-------------------

- El canje se registra solo si, **al cobrar**, el programa existe, el código es de ese programa
  (regla con código o tarjeta) y la orden tiene al menos una línea de descuento del programa. Si
  no, los campos quedan vacíos.
- Mientras la orden está en borrador (mesa abierta, enviada a cocina) el canje se conserva aunque
  todavía no haya línea de descuento.
- Un dato inválido nunca impide que la orden se sincronice.
- En órdenes pagadas, los datos del canje no se pueden modificar.

Pruebas
-------

Las pruebas automáticas de la lógica del servidor están en ``tests/test_discount_code.py`` (22
casos). Se corren en una base de pruebas, nunca en una base real, con
``odoo -d <base_de_pruebas> -i pos_discount_code --test-enable --test-tags /pos_discount_code --stop-after-init``.

El popup se prueba a mano en una caja, recargándola después de actualizar el módulo:

1. Código válido sobre la compra mínima: línea de descuento y aviso con el valor.
2. El mismo código otra vez: «Este código ya fue aplicado en la orden.»
3. Otro código: aviso de reemplazo en la vista previa; queda solo el nuevo descuento.
4. Quitar la línea del descuento y volver a aplicar el código: el descuento vuelve.
5. Código inexistente, vencido o aún no vigente: error en el formulario.
6. Cupón o tarjeta de regalo válidos: vista previa con el saldo real.
7. Cédula con puntos: error de solo dígitos. Pasaporte con letras: pasa.
8. Código bajo la compra mínima, orden enviada a cocina, completar la compra y cobrar: canje
   registrado con su valor.
9. Cobrar con el código activado pero sin línea de descuento: la orden queda sin canje.
10. Caja con el ajuste desmarcado: aparece el «Enter Code» de Odoo.

Known issues / Roadmap
======================

- Devolver una venta con bono no reactiva el bono ni marca el canje como reversado.
- No hay vistas de consulta de canjes (listas, filtros); los datos se ven en cada orden.
- En el formulario de una orden pagada los campos del canje se ven editables, pero guardar un
  cambio da error: el servidor los bloquea.
- Las cajas que no se recarguen después de actualizar el módulo siguen con el JavaScript anterior.
- ``static/src/js/loyalty_adapter.js`` es el único archivo que usa el estado interno de
  ``pos_loyalty`` (``codeActivatedProgramRules``, ``couponPointChanges``, ``disabledRewards``,
  ``_code_activated_coupon_ids``) y sus métodos internos. Al actualizar Odoo es el archivo a revisar.
- Con ``odooleal`` instalado, su versión 19 solo deja aplicar recompensas cuando el programa Leal
  está activo en la orden, para cualquier programa. Mientras no se corrija en ese módulo, el
  descuento del bono no llega a la orden en las cajas sin Leal. Se valida en staging junto con
  ``odooleal``.

Changelog
=========

19.0.1.0.0
----------

- Migración a Odoo 19. El botón pasa a las acciones de la orden (**⋮**) con el nombre
  **Convenio To Plus** y reemplaza al «Enter Code» de ``pos_loyalty``.
- Los campos del canje se sincronizan con el modelo de la orden del POS; ya no se serializan a
  mano.
- El canje se valida al cobrar contra las líneas guardadas en el servidor: en 19 el POS solo envía
  las líneas nuevas o modificadas.
- Una orden en borrador conserva el canje aunque todavía no tenga línea de descuento (orden enviada
  a cocina antes de llegar a la compra mínima).
- Los tipos de documento llegan al POS con la configuración de la caja.

17.0.1.2.0
----------

- Estado del bono guardado según la fecha del canje.
- Tipos de documento enviados al POS desde Python; se quitaron Registro Civil, PEP y PPT.
- Solo dígitos en los tipos numéricos (caja) y limpieza de separadores (servidor).
- Acceso a ``pos_loyalty`` concentrado en ``loyalty_adapter.js``, con revisión de compatibilidad.
- Corregido: al recargar la caja, las órdenes abiertas perdían el código aplicado.

17.0.1.1.0
----------

- Valor del descuento calculado en el servidor.
- Solo se registran bonos aplicados (programa, código y línea de recompensa).
- Fecha de canje en UTC.
- Un programa inexistente o un dato inválido ya no impiden sincronizar la orden.
- Cupones y tarjetas de regalo validados desde el primer clic.
- Se puede volver a aplicar un código cuyo descuento quitó el cajero.

17.0.1.0.0
----------

- Versión inicial.

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
