===============
Telegram Alerts
===============

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

Envía **alertas de costos de productos a Telegram**. Cada producto puede tener un **costo de
referencia** y un **porcentaje de diferencia permitido**; una acción planificada diaria revisa todos
los productos y manda a uno o varios chats de Telegram la lista de los que tienen el costo por
fuera de ese umbral.

Sirve para detectar a tiempo un costo mal cargado o un cambio de precio de compra que no se
esperaba, sin tener que revisar los productos uno por uno.

Las alertas salen por un **bot de Telegram** propio del negocio. El módulo guarda la conexión (token
del bot y chats destino) y ofrece además una acción para enviar un mensaje de prueba y otra para
calcular la diferencia de productos puntuales.

**Table of contents**

.. contents::
   :local:

Installation
============

Dependencias
------------

- Módulos de Odoo: ``base`` y ``product``. No depende de otros módulos de este repositorio.
- Librería de Python ``requests``, que ya viene con Odoo (en la imagen ``odoo:19.0`` está la versión
  2.31.0). No hay que instalar nada adicional.
- **API de Telegram para bots.** El servidor de Odoo debe poder salir a internet hacia
  ``https://api.telegram.org``. Hace falta un bot creado con **@BotFather** (que entrega el token) y
  que ese bot pueda escribir en cada chat destino: el usuario tiene que haberle iniciado una
  conversación, o el bot tiene que estar agregado al grupo.

Pasos de instalación
--------------------

Instalar **Telegram Alerts** desde *Aplicaciones*. La instalación crea:

- el menú **Telegram Alerts › Configuration**;
- una conexión de ejemplo llamada *Alertas Costos* con Custom ID ``cost_alert``;
- los campos *Reference Cost* y *Percentage Difference Cost* en el producto;
- tres acciones de servidor (*Calculate Difference Percentage*, *Send Cost Differences* y *Send
  Telegram Alert*) y la acción planificada diaria *Send Cost Differences*, activa desde el
  momento de la instalación.

Después de instalar, revisar la conexión *Alertas Costos* (ver *Configuración*) antes de que corra
la acción planificada.

Migración desde Odoo 17
-----------------------

El nombre técnico del módulo, del modelo ``telegram.alerts.config`` y de los campos de producto
(``reference_cost``, ``percentage_difference_cost``) no cambian respecto de 17, así que los datos se
conservan sin script. Cambios de la migración: la vista de lista usa ``<list>`` en lugar de
``<tree>``, la acción planificada ya no lleva ``numbercall`` (en 19 se repite hasta que se desactiva)
y se quitaron los archivos de ejemplo del andamiaje de Odoo (``models/models.py``, controlador,
``views/views.xml``, ``views/templates.xml`` y ``demo/demo.xml``), que en 17 estaban completamente
comentados. La etiqueta del campo *Percentage Difference Cost* corrigió su ortografía.

Configuration
=============

Conexión con Telegram
---------------------

Ir a **Telegram Alerts › Configuration** y abrir la conexión *Alertas Costos* (o crear una con
**Nuevo**). Todos los campos son obligatorios y ninguno tiene valor por defecto en el formulario.

.. figure:: ../static/description/01_configuracion.png
   :alt: Telegram Alerts › Configuration: campos de la conexión (token y chats difuminados)

   Telegram Alerts › Configuration: campos de la conexión (token y chats difuminados)

- **Custom ID** (``identifier``). Obligatorio. Es la clave con la que las acciones encuentran la
  conexión. La acción planificada y la acción *Send Cost Differences* buscan exactamente
  ``cost_alert``: si se cambia, dejan de enviar y fallan con *Telegram configuration not found*.
- **Name** (``name``). Obligatorio. Nombre descriptivo; no interviene en el envío.
- **Telegram Bot Token** (``token``). Obligatorio. El token que entrega @BotFather. Se muestra
  enmascarado en pantalla.
- **User IDs (comma-separated)** (``user_ids``). Obligatorio. Identificadores de chat de Telegram,
  separados por coma. Pueden ser usuarios (número positivo) o grupos (número negativo). Los
  espacios alrededor de cada coma se ignoran. Cada alerta se envía a todos.
- **Testing Message** (``msg_test``). Obligatorio. Texto que envía la acción de prueba.

Para probar la conexión, abrir el registro y, en el engranaje junto al nombre, elegir **Send
Telegram Alert**. Envía el *Testing Message* a cada chat de *User IDs*. Si no hay error, la
conexión funciona.

.. figure:: ../static/description/02_mensaje_prueba.png
   :alt: Acción Send Telegram Alert en el engranaje del registro de conexión

   Acción Send Telegram Alert en el engranaje del registro de conexión

Umbral de costo por producto
----------------------------

En el formulario del producto (por ejemplo desde **Punto de venta › Productos › Productos**),
pestaña *Información general*, debajo de *Costo*, aparecen dos campos nuevos. Un producto solo
entra en la revisión diaria si tiene **los dos** con valor distinto de cero.

.. figure:: ../static/description/03_producto.png
   :alt: Formulario de producto: Costo, Reference Cost y Percentage Difference Cost

   Formulario de producto: Costo, Reference Cost y Percentage Difference Cost

- **Reference Cost** (``reference_cost``). Opcional; 0 por defecto. El costo esperado del producto.
- **Percentage Difference Cost** (``percentage_difference_cost``). Opcional; 0 por defecto. Umbral
  expresado **como fracción entre 0 y 1**: 0,10 significa 10 %. Un valor fuera de ese rango no se
  puede guardar (*The Percentage Difference Cost must be between 0 and 1*). Con la interfaz en
  español el separador decimal es la coma: escribir ``0,10``, no ``0.10``.

El campo *Porcentaje de variación* que se ve en la misma pantalla no es de este módulo (lo agrega
``purchase_price_validation``) y usa otra escala.

Acción planificada
------------------

**Ajustes › Técnico › Automatización › Acciones planificadas** (requiere el modo desarrollador),
registro **Send Cost Differences**.

.. figure:: ../static/description/05_accion_planificada.png
   :alt: Acción planificada Send Cost Differences: intervalo, activo y código

   Acción planificada Send Cost Differences: intervalo, activo y código

- **Ejecutar cada**: 1 día, valor que instala el módulo. La hora de envío es la de *Siguiente
  fecha de ejecución*.
- **Activo**: encendida al instalar. Apagarla detiene la alerta diaria.
- **Código**: ``model.send_cost_differences('cost_alert')``, es decir, usa la conexión con Custom ID
  ``cost_alert``.

**Atención:** la conexión de ejemplo y la acción planificada se cargan sin ``noupdate``. Cada vez
que se actualiza el módulo, Odoo vuelve a escribir los valores del archivo de datos: el token, los
chats y el mensaje de *Alertas Costos*, y el intervalo y el estado *Activo* de la acción
planificada. Hay que revisarlos después de cada actualización (ver *Limitaciones conocidas*).

Usage
=====

Flujo
-----

1. Cargar en cada producto a vigilar su *Reference Cost* y su *Percentage Difference Cost*.
2. Una vez al día la acción planificada revisa todos los productos activos que tienen los dos
   campos distintos de cero y compara el costo actual (*Costo*) con el de referencia.
3. Si hay productos por fuera del umbral, envía **un solo mensaje** a cada chat de la conexión
   ``cost_alert``, con el encabezado *Productos con costo por fuera del umbral* y una línea por
   producto: nombre, costo actual y diferencia en porcentaje.
4. Si ningún producto está fuera del umbral, no se envía nada.

La diferencia es el valor absoluto de (referencia − costo) / costo × 100, y se compara con el umbral × 100.
Un producto con diferencia exactamente igual al umbral no se informa.

Acciones manuales en productos
------------------------------

En la lista de productos, al seleccionar uno o más, el menú **Acciones** muestra dos opciones del
módulo. Las dos envían a Telegram en cuanto se eligen, sin pedir confirmación.

.. figure:: ../static/description/04_acciones_producto.png
   :alt: Productos › Acciones: Calculate Difference Percentage y Send Cost Differences

   Productos › Acciones: Calculate Difference Percentage y Send Cost Differences

- **Send Cost Differences** hace exactamente lo mismo que la acción planificada, en el momento.
  **No tiene en cuenta la selección**: revisa todos los productos con umbral configurado.
- **Calculate Difference Percentage** envía **un mensaje por cada producto seleccionado** con la
  diferencia entre el costo de referencia y el costo (con signo), sin comparar contra el umbral.
  El mensaje no incluye el nombre del producto, así que conviene usarla con un solo producto a la
  vez. Usa la **primera conexión** que encuentre, sin importar su Custom ID.

Casos especiales
----------------

- **Producto con costo en cero** y umbral configurado: la revisión diaria lo incluye igual en el
  mensaje, como *nombre with cost: 0.0*, para avisar que le falta el costo.
  *Calculate Difference Percentage* responde *Standard price is zero, cannot calculate
  difference*.
- **Productos archivados**: no se revisan.
- **Varias conexiones**: la revisión diaria usa solo la de Custom ID ``cost_alert``. *Send Telegram
  Alert* prueba la conexión abierta (o las seleccionadas en la lista).

Solución de problemas
---------------------

- **Error *Telegram configuration not found*.** No existe una conexión con Custom ID ``cost_alert``
  (o ninguna conexión, en el caso de *Calculate Difference Percentage*). Crearla o corregir el
  Custom ID.
- **Error *Client Error ... for url: https://api.telegram.org/...* al enviar.** Telegram rechazó
  el envío. Las causas habituales son un token inválido o revocado (generar uno nuevo con
  @BotFather), un chat de *User IDs* incorrecto, un bot que no está en el grupo o un usuario que
  nunca le escribió al bot. También lo provoca una coma sobrante al final de la lista, porque se
  intenta enviar a un chat vacío. El texto del error incluye el token: no compartirlo tal cual.
- **Llegó a unos chats y a otros no.** Los envíos son en orden; el primer chat que falla corta el
  resto. Corregir ese chat y volver a probar con *Send Telegram Alert*.
- **La alerta diaria dejó de llegar sin error visible.** Revisar en la acción planificada que
  siga *Activa*: Odoo 19 desactiva una acción planificada que falla al menos 5 veces seguidas
  durante más de 7 días. El detalle del fallo queda en el log del servidor.
- **La conexión volvió a tener otro token o otros chats.** Se actualizó el módulo y se recargaron
  los datos de instalación (ver *Configuración › Acción planificada*).
- **El servidor tarda o se queda esperando al enviar.** Ver *Limitaciones conocidas*: la llamada
  a Telegram no tiene tiempo límite.

Known issues / Roadmap
======================

Limitaciones conocidas
----------------------

- **Los datos de instalación pisan la configuración.** ``data/telegram_config.xml`` y la acción
  planificada de ``data/server_actions.xml`` no están en ``noupdate``. Al actualizar el módulo se
  restauran el token, los chats y el mensaje de *Alertas Costos*, y la acción planificada vuelve a
  quedar activa cada 1 día aunque se hubiera apagado o cambiado.
- **Token real en el repositorio.** ``data/telegram_config.xml`` trae un token de bot y dos chat id
  reales, que se cargan en cualquier base donde se instale el módulo. Mientras eso siga así, una
  base de pruebas con la acción planificada activa puede enviar mensajes a los chats reales.
- **Permisos abiertos.** ``security/ir.model.access.csv`` da lectura, escritura, creación y borrado
  del modelo ``telegram.alerts.config`` sin grupo, es decir, a todos los usuarios; el menú tampoco
  tiene grupo. El token se enmascara en pantalla (``password="true"``), pero cualquier usuario puede
  leerlo por la API.
- **Sin tiempo límite ni reintentos.** ``send_message`` llama a Telegram con ``requests.get`` sin
  ``timeout``. Si Telegram no responde, el proceso queda esperando. No hay reintentos: un fallo se
  informa como error y el siguiente intento es la próxima ejecución diaria.
- **El token aparece en los errores.** El token va dentro de la URL del pedido y
  ``raise_for_status()`` arma el mensaje de error con esa URL, así que queda visible en el diálogo de
  error y en el log del servidor.
- **Un fallo corta el envío.** ``resp.raise_for_status()`` lanza una excepción en el primer chat que
  falla y los chats siguientes no reciben el mensaje.
- **Errores técnicos al usuario.** Si falta la conexión se lanza ``ValueError``, no ``UserError``, así
  que el usuario ve un error del servidor en lugar de un aviso.
- **Textos sin traducir.** Etiquetas, menús, nombres de acciones y el mensaje de *Calculate
  Difference Percentage* están en inglés y el módulo no tiene carpeta ``i18n``; el encabezado del
  resumen diario está en español dentro del código.
- *Calculate Difference Percentage* no incluye el nombre del producto en el mensaje y toma la
  primera conexión que encuentra, no la ``cost_alert``.
- El ícono ``static/description/icon.png`` mide 1024x1024 px; la convención del proyecto es
  100x100 px.

Componentes
-----------

- ``models/telegram_alerts.py``: modelo ``telegram.alerts.config`` (la conexión) y el envío
  (``send_message``, ``send_alert``, ``send_alert_test``) a ``https://api.telegram.org/bot<token>/sendMessage``,
  en texto plano.
- ``models/product_template.py``: campos ``reference_cost`` y ``percentage_difference_cost`` en
  ``product.template``, la validación 0–1 y los métodos ``calculate_difference_percentage`` y
  ``send_cost_differences(identifier)``.
- ``views/telegram_alerts_views.xml``: lista, formulario, acción y menú **Telegram Alerts ›
  Configuration**.
- ``views/product_view.xml``: los dos campos dentro del grupo ``group_standard_price`` del formulario
  de producto.
- ``data/server_actions.xml``: las tres acciones de servidor y la acción planificada diaria.
- ``data/telegram_config.xml``: la conexión *Alertas Costos* (``cost_alert``).

Notas para mantenimiento
------------------------

- El Custom ID ``cost_alert`` está escrito en dos lugares de ``data/server_actions.xml`` (acción de
  servidor y acción planificada). Si se renombra, hay que cambiar los dos.
- La acción planificada corre con el usuario *OdooBot*, que es quien lee los costos de los
  productos.
- El módulo no tiene tests automáticos. Para probar sin enviar a chats reales, usar un bot y un
  chat de prueba en la conexión, o apagar la acción planificada en la base de pruebas.

Credits
=======

Authors
-------

- Libertario Coffee Roasters

Contributors
------------

- Libertario Coffee Roasters
