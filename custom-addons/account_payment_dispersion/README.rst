=========================
Account Payment Dispersal
=========================

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

Base de la dispersión de pagos a proveedores para Colombia. Deja en Odoo los datos que necesita un
archivo de dispersión bancaria y guarda el historial de las dispersiones hechas.

- **Bancos colombianos.** Carga 68 bancos de Colombia con su **Código** de banco, un campo nuevo
  distinto del BIC que es el que piden los archivos de dispersión.
- **Tipo de cuenta.** Agrega el campo **Tipo de cuenta** (*Sin cuenta*, *Cuenta corriente*, *Cuenta
  de ahorro*, *Cuenta nómina*) a las cuentas bancarias de los contactos.
- **Pagos a proveedor.** El pago saliente muestra el tipo de cuenta de la cuenta bancaria del
  proveedor, sin tener que abrirla.
- **Historial de dispersiones.** Un registro por dispersión con el archivo generado, el diario y los
  pagos incluidos, en solo lectura.

Este módulo no genera archivos por sí solo: los generan los módulos de cada banco
(``bancolombia_payment_dispersal``, ``banco_de_occidente_payment_dispersal``), que se apoyan en él.

**Table of contents**

.. contents::
   :local:

Configuration
=============

No hay ajustes que activar. Lo que hay que dejar bien cargado son los datos de bancos y cuentas.

**1. Código del banco.** Los 68 bancos colombianos se instalan con el código ya puesto. Para
revisarlo o cargarlo en un banco nuevo: *Contactos › Configuración › Cuentas bancarias › Bancos*,
campo **Código**.

.. figure:: ../static/description/01_banco_codigo.png
   :alt: Contactos › Configuración › Cuentas bancarias › Bancos: campo Código

   Contactos › Configuración › Cuentas bancarias › Bancos: campo Código

**2. Tipo de cuenta del proveedor.** En cada cuenta bancaria de proveedor que se vaya a pagar por
dispersión: *Contactos › Configuración › Cuentas bancarias › Cuentas bancarias*, abrir la cuenta y
elegir el **Tipo de cuenta**. El banco de la cuenta tiene que ser uno con **Código**.

.. figure:: ../static/description/02_cuenta_bancaria_tipo.png
   :alt: Contactos › Configuración › Cuentas bancarias › Cuentas bancarias: campo Tipo de cuenta

   Contactos › Configuración › Cuentas bancarias › Cuentas bancarias: campo Tipo de cuenta

La lista de cuentas bancarias trae la columna **Tipo de cuenta** (opcional, visible por defecto),
para revisar de un vistazo qué cuentas faltan.

.. figure:: ../static/description/03_lista_cuentas_bancarias.png
   :alt: Lista de cuentas bancarias con la columna Tipo de cuenta

   Lista de cuentas bancarias con la columna Tipo de cuenta

A tener en cuenta:

- **En Odoo 19 el tipo de cuenta no se ve en la ficha del contacto.** La pestaña *Facturación* del
  contacto muestra las cuentas bancarias como etiquetas, sin columnas. El tipo de cuenta se carga
  desde *Cuentas bancarias* (o abriendo la etiqueta).
- **Permisos.** Ver el historial necesita *Contabilidad / Facturación* (lee, crea y modifica, no
  borra) o *Contabilidad / Administrador* (todo). El menú de *Configuración* lo ve solo
  *Contabilidad / Administrador*.

Usage
=====

**En el pago a proveedor.** En *Facturación › Proveedores › Pagos*, un pago saliente con diario de
banco y un método que pida cuenta (por ejemplo *Manual Payment*) muestra la **Cuenta bancaria de
proveedor** y, debajo, su **Tipo de cuenta**. No se edita en el pago: viene de la cuenta bancaria.
Si sale vacío, hay que completarlo en la cuenta (ver *Configuración*).

.. figure:: ../static/description/04_pago_proveedor_tipo_cuenta.png
   :alt: Pago a proveedor: Tipo de cuenta debajo de la cuenta bancaria del proveedor

   Pago a proveedor: Tipo de cuenta debajo de la cuenta bancaria del proveedor

El pago a proveedor trae además una zona de pestañas vacía (``dispersion_banks``) donde los módulos
de cada banco agregan sus datos. Con solo este módulo instalado no se ve nada ahí.

**Historial de dispersiones.** *Facturación › Proveedores › Dispersiones bancarias* lista las
dispersiones hechas, con quién y cuándo las creó.

.. figure:: ../static/description/05_menu_dispersiones.png
   :alt: Facturación › Proveedores › Dispersiones bancarias

   Facturación › Proveedores › Dispersiones bancarias

El mismo historial está en *Facturación › Configuración › Pagos dispersos › Dispersiones bancarias*,
solo para *Contabilidad / Administrador*.

.. figure:: ../static/description/06_menu_configuracion.png
   :alt: Facturación › Configuración › Pagos dispersos › Dispersiones bancarias

   Facturación › Configuración › Pagos dispersos › Dispersiones bancarias

Cada dispersión guarda el archivo que se mandó al banco, el diario y los pagos que incluyó. Es de
solo lectura: no se crea ni se edita a mano, la crean los módulos de cada banco al generar el
archivo. Las dispersiones archivadas se ven con el filtro *Archivado* y una cinta roja.

.. figure:: ../static/description/07_formulario_dispersion.png
   :alt: Dispersión: archivo generado y pagos dispersos

   Dispersión: archivo generado y pagos dispersos

Known issues / Roadmap
======================

- **Los módulos que generan los archivos no están migrados a Odoo 19.**
  ``bancolombia_payment_dispersal`` y ``banco_de_occidente_payment_dispersal`` son los que llenan la
  pestaña ``dispersion_banks`` del pago y de la cuenta bancaria y crean las dispersiones. Hasta
  migrarlos, este módulo solo guarda datos (código de banco, tipo de cuenta) y muestra el historial.
- **Tipo de cuenta fuera de la ficha del contacto.** En 17 el tipo de cuenta salía como columna en
  la lista de cuentas de la ficha del contacto. En 19 esa lista son etiquetas (``many2many_tags_banks``)
  y ya no hay columna. Por eso la vista heredada pasó a la lista de cuentas bancarias.
- **Vista con xmlid reutilizado.** ``account_payment_dispersion_inherit_view_partner_property_form``
  era en 17 una vista de ``res.partner`` y en 19 es de ``res.partner.bank`` (hereda de
  ``base.view_partner_bank_tree``). Antes del ``-u`` en STG/producción, comprobar que ninguna vista
  herede de ella:
  ``SELECT id, name, model FROM ir_ui_view WHERE inherit_id = (SELECT res_id FROM ir_model_data WHERE module = 'account_payment_dispersion' AND name = 'account_payment_dispersion_inherit_view_partner_property_form');``
  En local da 0 filas.
- **Traducción de los valores de Tipo de cuenta.** En los ``.po`` heredados de 16, las opciones
  (*Sin Cuenta*, *Cuenta corriente*, *Cuenta de ahorro*, *Cuenta nómina*) estaban marcadas como
  texto de código (``#: code:``), y Odoo no las aplicaba a la selección. En 19 se marcaron como
  ``model:ir.model.fields.selection`` con el mismo texto. El ``-u`` no pisa un nombre que ya esté en
  la base: solo completa los idiomas que faltan (``TranslationImporter.save``, ``overwrite=False``).
  Las capturas 02 a 04 se tomaron antes del arreglo y muestran *Savings Account*. Para revisar en
  STG antes y después del ``-u``:
  ``SELECT d.name, s.name FROM ir_model_fields_selection s JOIN ir_model_data d ON d.model = 'ir.model.fields.selection' AND d.res_id = s.id WHERE d.module = 'account_payment_dispersion';``
- **ACL de solo lectura.** ``security/ir.model.access.csv`` da lectura a
  ``account.group_account_readonly`` sobre las dispersiones y sus campos. En 17 no existía. Se
  mantiene: es el mismo patrón que usa el core para ``account.payment`` y permite que un usuario de
  solo lectura (auditor) vea el historial sin poder modificarlo.
- **``data/res.bank.csv`` no se carga.** No está en ``data`` del manifiesto. Los bancos salen de
  ``data/res_bank_data.xml`` (``noupdate``, así que un ``-u`` no corrige cambios hechos a mano).
- **Columna "Activo" vacía en la lista de dispersiones.** La lista declara ``active`` con
  ``invisible="1"``, que en listas oculta la celda pero no la columna (igual en 17). Se arregla con
  ``column_invisible="1"``.
- **Textos del modelo en inglés.** El chatter de la dispersión dice "It shows the dispersions that
  have taken place over time. creado": usa la ``_description`` del modelo, que es una frase larga.
- **Cuentas no fiables.** En 19 una cuenta bancaria nueva sale como *No fiable* (etiqueta roja, sin
  *Enviar dinero*). Odoo solo bloquea el pago si el método exige cuenta; ningún método de Community
  lo exige, pero los módulos de banco podrían hacerlo.
- ``static/description/icon.png`` mide 300x300 px; los módulos del core usan 100x100 px.

Credits
=======

Authors
-------

- Firefly Software Consulting S.A.S

Contributors
------------

- Firefly Software Consulting S.A.S (juan.zuluaga@firefly-e.com)
