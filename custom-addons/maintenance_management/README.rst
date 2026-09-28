=================================
Gestión Integral de Mantenimiento
=================================

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

Amplía la aplicación **Mantenimiento** de Odoo para llevar la trazabilidad de los equipos de las
tiendas (neveras, molinos, máquinas de espresso) y el control de cada intervención:

- **Equipos identificados**: cada equipo recibe un número de activo consecutivo (``ACT00001``…), un
  número de serie automático si no se digita uno, la tienda donde está y el cliente asociado (por
  ejemplo, un equipo en comodato).
- **Código QR y hoja de vida**: el QR del equipo abre una página del portal con su ficha técnica,
  indicadores (MTBF, MTTR, costo acumulado) y el historial de mantenimientos. Se imprime como
  etiqueta PDF para pegarla en el equipo.
- **Solicitudes más completas**: referencia consecutiva (``INC00001``…), condición del equipo,
  ubicación del mantenimiento, diagnóstico y un reporte imprimible *Orden de Mantenimiento*.
- **Checklist por categoría**: los ítems de una plantilla se copian a cada solicitud del equipo, y
  la solicitud no se puede cerrar mientras queden ítems sin marcar.
- **Costos**: líneas de costo por solicitud, cargadas a mano o traídas de una orden de compra, con
  el total por solicitud y el acumulado por equipo.

Existe para que el área de mantenimiento sepa qué equipo hay en cada tienda, qué se le hizo y
cuánto costó, y para que un técnico pueda consultar la historia del equipo escaneando su QR.

**Table of contents**

.. contents::
   :local:

Installation
============

Dependencias
------------

- Módulos de Odoo Community: ``maintenance``, ``portal``, ``purchase`` y ``stock``. No requiere librerías
  de Python adicionales: el QR se genera con el generador de códigos de barras que ya trae Odoo.

Pasos de instalación
--------------------

Instalar el módulo desde *Aplicaciones* (aparece como *Gestión Integral de Mantenimiento*). La
instalación crea:

- las secuencias *Mantenimiento: Número de Activo* (prefijo ``ACT``) y *Mantenimiento:
  Incidencia/Solicitud* (prefijo ``INC``), ambas de 5 dígitos y compartidas por todas las compañías;
- el parámetro del sistema ``maintenance_management.enforce_checklist`` con valor ``True``;
- el menú *Mantenimiento › Configuración › Plantillas de Checklist*;
- la acción *Asignar Nº de activo, QR y serial* en el menú *Acción* de los equipos;
- los reportes *Etiqueta QR del Equipo* y *Orden de Mantenimiento*.

Los equipos que ya existían antes de instalar el módulo quedan sin número de activo, sin serie
automática y sin token de portal (el QR no abre la hoja de vida). Para completarlos, en
*Mantenimiento › Equipo* seleccionarlos en la lista y ejecutar *Acción › Asignar Nº de
activo, QR y serial*. Solo llena lo que falta, así que se puede repetir sin riesgo.

En bases con datos de demostración se cargan además tres categorías (*Neveras*, *Molinos*,
*Máquinas de espresso*) con su plantilla de checklist.

Migración desde Odoo 17
-----------------------

El módulo conserva el nombre, los modelos y los nombres técnicos de los campos de la versión 17,
por lo que los datos existentes se mantienen sin script de migración. Los cambios de la migración
fueron de forma: la restricción de número de activo único pasó a la sintaxis ``models.Constraint``,
las vistas de lista usan ``list`` en lugar de ``tree`` y la hoja de vida del portal dejó de mostrar el
campo *Ubicación* (``location``) del equipo, que ya no existe en ``maintenance`` de Odoo 19. La tienda
se sigue mostrando como *Tienda / Almacén*.

Configuration
=============

Plantillas de checklist
-----------------------

Ir a *Mantenimiento › Configuración › Plantillas de Checklist* y crear una plantilla por categoría
de equipo. Las categorías se administran en *Mantenimiento › Configuración › Categorías del
equipo*.

.. figure:: ../static/description/01_configuracion_checklist.png
   :alt: Mantenimiento › Configuración › Plantillas de Checklist: categoría e ítems de la plantilla

   Mantenimiento › Configuración › Plantillas de Checklist: categoría e ítems de la plantilla

- **Nombre**. Obligatorio. Solo sirve para identificar la plantilla.
- **Categoría de equipo**. Opcional en el formulario, pero una plantilla sin categoría nunca se
  aplica: la solicitud busca la plantilla por la categoría de su equipo.
- **Ítems**. Opcional. Cada ítem tiene un texto obligatorio; el orden se ajusta arrastrando la
  manija de la izquierda y es el mismo en que aparecen en la solicitud.

A tener en cuenta:

- El menú solo lo ven los usuarios del grupo **Responsable de los equipos** (``maintenance.group_equipment_manager``).
- Si hay varias plantillas para la misma categoría, se usa **solo la primera** que encuentra Odoo.
  Conviene mantener una plantilla por categoría.
- Cambiar una plantilla no modifica las solicitudes que ya tienen su checklist cargado.

Checklist obligatorio para cerrar
---------------------------------

El control que impide cerrar una solicitud con ítems pendientes se gobierna con el parámetro del
sistema ``maintenance_management.enforce_checklist``, en *Ajustes › Técnico › Parámetros del
sistema* (requiere el modo de desarrollador).

- Valor por defecto: ``True`` (activo). Con ``1``, ``true`` o ``yes`` (sin importar mayúsculas) el control
  está activo; con cualquier otro valor, por ejemplo ``False``, queda desactivado.
- El parámetro se crea una sola vez al instalar: actualizar el módulo no pisa el valor que se haya
  cambiado.

Datos del equipo
----------------

No hay más ajustes. La tienda (*Almacén/Tienda*) y el cliente se indican en cada equipo, en la
pestaña *Ficha técnica* (ver *Uso*). El código de la tienda que entra en el número de serie es el
**Nombre corto** del almacén en *Inventario › Configuración › Almacenes*.

Usage
=====

Registrar un equipo
-------------------

En *Mantenimiento › Equipo* crear el equipo con su nombre y categoría. En la pestaña
**Ficha técnica** indicar la tienda (*Almacén/Tienda*) y, si aplica, el cliente. Al guardar, el
módulo asigna:

- el **Número de Activo** siguiente de la secuencia ``ACT``;
- el **Número de serie**, si se dejó vacío: las tres primeras letras de las dos primeras palabras
  del nombre (en mayúsculas, sin tildes y omitiendo artículos y preposiciones como *de*, *la*,
  *para*), más el código de la tienda y la fecha de registro ``AAAAMMDD``. Por ejemplo, *Nevera de
  cocina* en la tienda ``ZNG2`` registrada el 8 de mayo de 2025 queda ``NEVCOCZNG220250508``;
- el token de portal que usa el código QR.

.. figure:: ../static/description/02_equipo.png
   :alt: Ficha del equipo: botones del módulo, pestaña Ficha técnica y código QR

   Ficha del equipo: botones del módulo, pestaña Ficha técnica y código QR

Desde la ficha del equipo:

- **Hoja de Vida** abre la página del equipo en el portal.
- **Imprimir QR** genera la etiqueta PDF con el nombre, el número de activo, la serie, la categoría
  y el QR. La misma etiqueta sale de *Imprimir › Etiqueta QR del Equipo*, también para varios
  equipos seleccionados en la lista.
- **Costo total** muestra la suma de los costos de todas las solicitudes del equipo y, al
  pulsarlo, las lista.
- **Descargar QR**, debajo de la imagen, baja el QR como PNG (``QR_<número de activo>.png``).

En la búsqueda de equipos se puede filtrar por número de activo, tienda y cliente, y agrupar por
*Tienda* o *Cliente*.

Atender una solicitud
---------------------

Crear la solicitud en *Mantenimiento › Mantenimiento › Solicitudes de mantenimiento* y elegir el
equipo. En el formulario se cargan solos la **Ubicación del mantenimiento** (la tienda del equipo)
y el **Checklist** de la plantilla de su categoría. Al guardar se asigna la **Referencia** ``INC``.

.. figure:: ../static/description/03_solicitud_checklist.png
   :alt: Solicitud de mantenimiento: referencia, ubicación, condición del equipo y checklist

   Solicitud de mantenimiento: referencia, ubicación, condición del equipo y checklist

El técnico registra la **Condición del equipo** (Bueno, Regular o Malo), marca los ítems del
checklist a medida que los hace (con una nota opcional por ítem) y describe lo realizado en la
pestaña **Diagnóstico**.

Mientras quede algún ítem sin marcar, la solicitud no puede pasar a una etapa marcada como
*Solicitud lista* (en las etapas estándar, *Reparado* y *Desechar*). Odoo muestra el aviso y no guarda el
cambio de etapa.

.. figure:: ../static/description/04_bloqueo_checklist.png
   :alt: Intento de cerrar una solicitud con ítems pendientes del checklist

   Intento de cerrar una solicitud con ítems pendientes del checklist

Registrar los costos
--------------------

En la pestaña **Costos** se agregan las líneas de costo a mano (detalle, producto, cantidad y
valor) o se traen de una compra: elegir la **Orden de compra** y pulsar **Traer costos de OC**.
Cada línea de la orden se copia con su descripción, producto, cantidad y subtotal sin impuestos.
El **Costo total** de la solicitud se suma solo y alimenta el costo acumulado del equipo.

.. figure:: ../static/description/05_costos.png
   :alt: Pestaña Costos: orden de compra, botón Traer costos de OC, líneas y costo total

   Pestaña Costos: orden de compra, botón Traer costos de OC, líneas y costo total

Para imprimir la solicitud usar *Imprimir › Orden de Mantenimiento*: incluye equipo, fechas,
técnico, condición, checklist, costos y observaciones.

Hoja de vida en el portal
-------------------------

Al escanear el QR (o pulsar *Hoja de Vida*) se abre la página del equipo. La puede ver cualquier
persona que tenga el QR, sin iniciar sesión, porque el enlace incluye el token de acceso del
equipo. Un usuario interno con permiso sobre el equipo la ve también sin el token.

.. figure:: ../static/description/06_hoja_vida_portal.png
   :alt: Hoja de vida del equipo en el portal

   Hoja de vida del equipo en el portal

Casos especiales
----------------

- **Equipo sin tienda**: el serial se arma sin código de tienda, y la solicitud queda sin ubicación
  hasta que se elija una.
- **Cambiar el equipo de una solicitud**: la ubicación y el checklist solo se cargan si están
  vacíos. Si ya había un checklist, no se reemplaza por el de la nueva categoría.
- **Mantenimiento preventivo recurrente**: la solicitud siguiente que crea Odoo al cerrar la actual
  recibe una referencia nueva, pero **llega sin checklist y sin costos**, por lo que el bloqueo no
  la afecta.
- **Traer costos de OC dos veces**: cada pulsación vuelve a copiar todas las líneas; hay que borrar
  las duplicadas a mano.

Solución de problemas
---------------------

- **"No puede marcar como Realizado: el checklist de la solicitud … tiene ítems pendientes."**
  Marcar los ítems que faltan en la pestaña *Checklist* y volver a cambiar la etapa. Después del
  aviso el formulario queda mostrando la etapa nueva sin guardar: descartar los cambios (ícono ✖
  junto al nombre) antes de seguir editando, o completar el checklist y guardar.
- **La solicitud no trae checklist.** El equipo no tiene categoría, o su categoría no tiene
  plantilla. El checklist se carga solo al elegir el equipo en el formulario; las solicitudes
  creadas por importación o por código no lo reciben.
- **Al escanear el QR se pide iniciar sesión.** El equipo no tenía token de portal cuando se
  imprimió o descargó el QR (pasa con equipos anteriores a la instalación). Ejecutar *Acción ›
  Asignar Nº de activo, QR y serial* sobre el equipo y volver a imprimir la etiqueta.
- **El QR abre una dirección que no carga desde el celular.** La URL del QR se arma con el
  parámetro ``web.base.url``; debe ser la dirección pública del servidor. Si el servidor atiende
  varias bases sin filtro de base de datos (``dbfilter``), el enlace responde *404* a quien no tiene
  sesión.
- **El número de serie salió con caracteres raros**, por ejemplo ``DOC-…``: los signos sueltos del
  nombre (un guion entre espacios) cuentan como palabra. Corregir la serie a mano; el módulo solo
  la calcula si está vacía.

Known issues / Roadmap
======================

Limitaciones conocidas
----------------------

- **El checklist solo se carga desde el formulario.** Lo trae el cambio de equipo en la pantalla;
  las solicitudes creadas por importación, por código o como repetición de un preventivo
  recurrente quedan sin checklist y, por lo tanto, sin bloqueo al cerrar.
- **El bloqueo solo revisa el cambio de etapa.** Una solicitud creada directamente en una etapa de
  cierre no se valida.
- **Traer costos de OC no evita duplicados.** Cada pulsación copia de nuevo todas las líneas de la
  orden, aunque ya se hayan traído.
- **Regla del número de serie sin confirmar.** El código la marca como pendiente de validar con el
  negocio (longitud de las abreviaturas, separadores, fecha de creación o de puesta en marcha). El
  parámetro ``maintenance_management.serial_pattern`` que menciona el código **no existe** en la base
  ni cambia nada: la regla está fija en ``_compute_or_default_serial()``. La serie tampoco es única.
- **La hoja de vida es pública para quien tenga el QR.** Muestra la ficha completa, incluidos el
  cliente, el proveedor y el técnico responsable. El módulo no ofrece una forma de renovar el token
  desde la interfaz si una etiqueta se pierde.
- **Permisos amplios.** Cualquier usuario interno puede crear, modificar y borrar plantillas de
  checklist y líneas de costo; el menú de plantillas es lo único restringido a *Responsable de los
  equipos*.
- **Una plantilla por categoría.** Si hay varias, se usa la primera que encuentra Odoo.
- **Columna *Moneda* vacía en las líneas de costo.** El campo está marcado ``invisible="1"`` dentro de
  la lista; en Odoo 19 eso oculta el valor pero deja la columna. Es solo estético.
- **Textos fijos en español.** Las vistas, los reportes y los mensajes están escritos en español en
  el código y el módulo no trae carpeta ``i18n/``: un usuario con Odoo en otro idioma los ve igual.
- Falta ``static/description/icon.png``: en *Aplicaciones* se ve el ícono genérico de Odoo.

Componentes
-----------

- ``models/maintenance_equipment.py``: número de activo, tienda, cliente, QR (``portal.mixin``), costo
  acumulado, serie por defecto y las acciones de los botones y de *Asignar Nº de activo, QR y
  serial*. El código de tienda del serial sale de ``_get_store_code()``, aislado para poder cambiar
  su origen sin tocar lo demás.
- ``models/maintenance_request.py``: referencia, condición, ubicación, checklist, costos, carga de la
  plantilla (``_onchange_equipment_id``), bloqueo de cierre (``write``) y ``action_bring_costs_from_po``.
- ``models/maintenance_checklist.py``: plantillas, ítems de plantilla e ítems de la solicitud.
- ``models/maintenance_request_cost_line.py``: líneas de costo, con enlace a la línea de compra de
  origen.
- ``controllers/portal.py`` y ``views/maintenance_portal_templates.xml``: la ruta ``/my/equipment/<id>``
  y la hoja de vida. Valida el acceso con ``_document_check_access`` (token o permisos del usuario).
- ``report/qr_label_report.xml`` y ``report/maintenance_report.xml``: etiqueta QR y orden de
  mantenimiento. El QR va embebido como imagen, sin servicio externo.
- ``data/``: secuencias ``ACT`` e ``INC``, el parámetro ``enforce_checklist`` y la acción de servidor.
- ``demo/demo_data.xml``: categorías y plantillas de ejemplo, solo en bases con demostración.

Notas para mantenimiento
------------------------

- **Sin tests automáticos.** El módulo no tiene carpeta ``tests/``; todo se valida a mano.
- **El QR depende de ``web.base.url``.** Se calcula al vuelo (no se guarda) con la URL base y el token
  del equipo. Si cambia la dirección del servidor, las etiquetas ya impresas apuntan a la
  dirección vieja.
- **Traer costos automáticamente.** ``action_bring_costs_from_po()`` está aislado para poder llamarlo
  más adelante al confirmar la compra o desde un cron; hoy es solo manual.
- **Migración 17 → 19.** El campo ``location`` de ``maintenance.equipment`` desapareció del core en 19;
  si se vuelve a usar en la plantilla del portal, la hoja de vida falla con ``AttributeError``. En
  Odoo 19 el campo *Usado en la ubicación* del equipo lo agrega ``stock_maintenance`` y no lo usa este
  módulo.
- **Moneda de los costos.** La solicitud toma por defecto la moneda de la compañía activa al
  crearla, en lugar de un campo relacionado con su compañía, para no fallar si la solicitud no
  tiene compañía resuelta. Las líneas de costo usan la moneda de su solicitud.

Credits
=======

Authors
-------

- Maintenance Management

Contributors
------------

- Maintenance Management (autor declarado en el manifiesto)
