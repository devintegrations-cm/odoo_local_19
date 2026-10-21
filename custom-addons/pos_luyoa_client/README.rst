=============================
POS — Cliente Luyoa (lealtad)
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

Agrega al POS un botón **Cliente Luyoa** para identificar al cliente escaneando
el **QR de su tarjeta de lealtad digital** (Apple/Google Wallet) con la cámara
del dispositivo, consultarlo en la **API de Luyoa** y asignarlo a la orden para
facturarle.

El flujo completo desde cualquier botón (junto a *Nota*, en el submenú de los
3 puntos y en la pantalla de pago):

1. Se abre la cámara; el cajero apunta al QR de la tarjeta del cliente.
2. El sistema extrae el identificador del cliente de la URL de la tarjeta
   (``…/c/<customerUID>``) y consulta ``GET /customer/:customerUID`` en Luyoa con
   las credenciales del punto de venta.
3. El popup muestra los datos que devolvió Luyoa (nombre, correo, teléfono,
   sellos/saldo) y el contacto de Odoo que coincide, indicando por qué regla
   coincidió.
4. El cajero confirma. **Asignar cliente** si ya existe en Odoo, o **Crear y
   asignar** si no existe: se crea con los datos básicos de Luyoa (nombre,
   correo y teléfono) y se asigna a la orden.

El contacto de Odoo se busca, en este orden:

1. **Tarjeta ya vinculada**: el identificador de Luyoa guardado en el contacto
   (dato interno, no visible). Una tarjeta solo puede estar en un contacto.
2. **Correo** (sin distinguir mayúsculas).
3. **Nombre y teléfono juntos**.

Solo el nombre o solo el teléfono **no alcanzan** para asignar: dos personas
pueden compartirlos. La primera vez que el cliente se asigna o se crea, su
identificador de Luyoa queda guardado y los próximos escaneos lo encuentran
directo. Si el contacto encontrado ya está vinculado a **otra** tarjeta, no se
asigna ni se crea un duplicado: se pide revisarlo en Contactos.

5. Al asignarse se marca la orden para facturar.

Si el QR no corresponde a un cliente de Luyoa, hay dos contactos en Odoo que
coinciden (el popup lista los candidatos), el contacto está archivado, o falla
la credencial o la conexión, se muestra al cajero un mensaje claro con qué
hacer y **no se asigna nadie**.

Solo se identifica por QR, con la cámara del POS o de la tablet: no hay entrada
manual de identificadores. Las credenciales (Integration UID, Business UID y
token) solo las ve el responsable del POS y nunca llegan al navegador: la
consulta a Luyoa la hace el servidor.

**Table of contents**

.. contents::
   :local:

Configuration
=============

En **Punto de Venta → Configuración → Puntos de venta → (tu tienda) →
pestaña Configuración → Cliente Luyoa (lealtad)**:

1. Marque **Botón Luyoa** para mostrar el botón en el POS.
2. Complete las credenciales (todas obligatorias para usar el botón):

   - **URL del API**: ``https://demo.luyoa.com/api/external/v1`` (viene por defecto; es el entorno donde está registrado y habilitado el negocio, no la web de la tarjeta del cliente). Las credenciales solo valen en el entorno donde se generaron: al cambiar la URL el formulario muestra una advertencia.
   - **Integration UID**: identificador de la integración (partner). Lo entrega Luyoa al registrar el acceso a la API y debe ser el de la misma integración que generó el token; sin él la API responde ``401``.
   - **Business UID**: identificador del negocio, en el dashboard de Luyoa.
   - **Token**: token de autenticación del negocio, en el dashboard de Luyoa. Es información sensible: guárdela con cuidado.

Con el botón marcado, los cuatro campos son obligatorios para guardar la
configuración; además, si falta alguno, el popup informa exactamente qué falta
antes de consultar. Las credenciales solo las ve y edita el responsable del
POS (grupo *Punto de Venta / Administrador*).

.. figure:: ../static/description/01_configuracion.png
   :alt: Punto de Venta › Configuración › Puntos de venta › (tienda) › Configuración: 1. «Botón Luyoa»; 2. las cuatro credenciales

   Punto de Venta › Configuración › Puntos de venta › (tienda) › Configuración: 1. «Botón Luyoa»; 2. las cuatro credenciales

La cámara del navegador solo funciona sobre **HTTPS** (en desarrollo,
``localhost`` también sirve). En cajas sin cámara, el diálogo de escaneo del
core muestra el motivo y el cajero puede cerrarlo sin perder la orden.

Usage
=====

1. Con una orden abierta, toque el botón **Cliente Luyoa**:

   - En desktop: el icono cuadrado junto al botón *Nota*, o *Cliente Luyoa* en el submenú de los 3 puntos.
   - En pantallas pequeñas: el botón *Luyoa* de la barra de acciones (junto a *Cliente*).
   - En la pantalla de pago: el logo de Luyoa sobre el teclado numérico.

.. figure:: ../static/description/02_boton_orden.png
   :alt: Pantalla de la orden: botón Cliente Luyoa junto a Nota

   Pantalla de la orden: botón Cliente Luyoa junto a Nota

2. Se abre la cámara; apunte al QR de la tarjeta digital del cliente
   (Apple/Google Wallet). Si cancela la cámara, el popup queda abierto para
   reintentar.
3. Revise los datos mostrados (cliente de Luyoa y contacto de Odoo) y toque
   **Asignar cliente** o **Crear y asignar**. La orden queda con el cliente
   asignado y marcada para facturar.

Si el cliente ya existe en Odoo, el popup muestra los dos lados y por qué
coincidieron (tarjeta escaneada, correo, o nombre y teléfono):

.. figure:: ../static/description/03_cliente_encontrado.png
   :alt: Cliente de Luyoa que ya existe en Odoo: Asignar cliente

   Cliente de Luyoa que ya existe en Odoo: Asignar cliente

Si no existe, se ofrece crearlo con su nombre, correo y teléfono de Luyoa:

.. figure:: ../static/description/04_cliente_nuevo.png
   :alt: Cliente de Luyoa que no existe en Odoo: Crear y asignar

   Cliente de Luyoa que no existe en Odoo: Crear y asignar

Cuando el QR no es de una tarjeta de Luyoa, o falla la credencial o la
conexión, el popup explica el motivo y ofrece **Escanear de nuevo** o
**Reintentar**; no se asigna nadie:

.. figure:: ../static/description/05_qr_invalido.png
   :alt: QR que no corresponde a un cliente de Luyoa

   QR que no corresponde a un cliente de Luyoa

El mismo flujo se abre desde la pantalla de pago:

.. figure:: ../static/description/06_boton_pago.png
   :alt: Pantalla de pago: logo de Luyoa sobre el teclado numérico

   Pantalla de pago: logo de Luyoa sobre el teclado numérico

Con dos contactos de Odoo que matchean al mismo cliente, el popup lista los
candidatos y no deja asignar hasta resolverlo en *Contactos*. Un contacto
archivado, o uno ya vinculado a otra tarjeta de Luyoa, también bloquea la
asignación con el aviso correspondiente.

Known issues / Roadmap
======================

Upgrade pendiente: registrar transacciones en Luyoa
---------------------------------------------------

El módulo hoy **solo identifica** al cliente (lectura). El API de Luyoa
expone tres endpoints de escritura para un futuro upgrade, documentados acá
para no tener que volver al spec:

- ``POST /transaction`` — registrar una compra (suma sellos/saldo según las
  reglas del negocio en Luyoa). Campos: ``customerUID`` (opcional: sin él la
  transacción se guarda solo para análisis), ``businessBranchUID`` (obligatorio:
  mapear cada ``pos.config`` → un branch de Luyoa con ``GET /business-branch``),
  ``total`` (≥ 0), ``reference`` (nº de ticket, único), ``createdAt`` (ISO 8601,
  opcional) y ``items[]`` (``code``, ``name``, ``quantity`` ≥ 1, ``priceEach`` ≥ 0).
  Respuesta: ``{"success": true, "data": "…"}``.
- ``POST /transaction/bulk`` — hasta 100 transacciones por llamada
  (``{"transactions": [...]}``). Respuesta con ``processed`` / ``successful`` /
  ``failed`` y errores por ``reference``: sirve para subir el día completo al
  cierre de caja.
- ``POST /reward/redeem/:rewardUID`` — canjear un reward del cliente. Cuerpo:
  ``{"businessBranchUID": "…"}``. Los rewards disponibles por cliente vienen en
  ``GET /customer/:customerUID`` (``data.rewards[]``: ``uid``, ``name``, ``type`` en
  ``FREE_PRODUCT`` | ``DISCOUNT`` | ``OTHER``, ``expiresAt`` en ms y
  ``externalReference`` para ligarlo a un producto del POS).

Punto de enganche natural: la validación del pago (``validateOrder``) para
``/transaction``, y el cierre de caja para el bulk. La UI ya conoce el
``customerUID`` (se guarda en ``res.partner.luyoa_customer_uid`` al asignar).

Límites conocidos
-----------------

- **Sin webhook**: Luyoa no notifica cambios (puntos canjeados en su app,
  por ejemplo); todo lo que el POS muestra es lo que consulta al escanear.
- **Sin historial de transacciones**: el API no expone ``GET /transaction``, no
  se puede conciliar desde Odoo.
- **Nombre y teléfono**: el teléfono se compara por dígitos con
  ``ILIKE '%<dígitos>%'``; uno guardado en Odoo con espacios (``+52 55 1234 5678``)
  no coincide y el popup ofrece crear el cliente. El correo es la clave
  principal y la tarjeta vinculada resuelve los próximos escaneos.
- **Tarjeta vinculada no visible**: el identificador de Luyoa del contacto no
  se muestra en ninguna vista. Si hubiera que desvincular una tarjeta, hoy se
  hace por base de datos o modo desarrollador.
- **Sin catálogo de rewards**: solo se ven los rewards del cliente escaneado
  (vienen en su respuesta); no hay endpoint de catálogo.
- **Concurrencia**: dos cajas que crean el mismo cliente al mismo tiempo
  pueden dejar un duplicado; la restricción de unicidad impide que la misma
  tarjeta quede en dos contactos, y la próxima consulta informa el resto
  como ambiguo.

Credits
=======

Authors
-------

- Libertario Coffee

Contributors
------------

- Desarrollo Libertario (Miguel Bolivar) \<<devintegrations@libertariocoffee.com>\>
