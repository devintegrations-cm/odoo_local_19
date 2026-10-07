- **Los módulos que generan los archivos no están migrados a Odoo 19.**
  `bancolombia_payment_dispersal` y `banco_de_occidente_payment_dispersal` son los que llenan la
  pestaña `dispersion_banks` del pago y de la cuenta bancaria y crean las dispersiones. Hasta
  migrarlos, este módulo solo guarda datos (código de banco, tipo de cuenta) y muestra el historial.
- **Tipo de cuenta fuera de la ficha del contacto.** En 17 el tipo de cuenta salía como columna en
  la lista de cuentas de la ficha del contacto. En 19 esa lista son etiquetas (`many2many_tags_banks`)
  y ya no hay columna. Por eso la vista heredada pasó a la lista de cuentas bancarias.
- **Vista con xmlid reutilizado.** `account_payment_dispersion_inherit_view_partner_property_form`
  era en 17 una vista de `res.partner` y en 19 es de `res.partner.bank` (hereda de
  `base.view_partner_bank_tree`). Antes del `-u` en STG/producción, comprobar que ninguna vista
  herede de ella:
  `SELECT id, name, model FROM ir_ui_view WHERE inherit_id = (SELECT res_id FROM ir_model_data WHERE module = 'account_payment_dispersion' AND name = 'account_payment_dispersion_inherit_view_partner_property_form');`
  En local da 0 filas.
- **Traducción de los valores de Tipo de cuenta.** En los `.po` heredados de 16, las opciones
  (*Sin Cuenta*, *Cuenta corriente*, *Cuenta de ahorro*, *Cuenta nómina*) estaban marcadas como
  texto de código (`#: code:`), y Odoo no las aplicaba a la selección. En 19 se marcaron como
  `model:ir.model.fields.selection` con el mismo texto. El `-u` no pisa un nombre que ya esté en
  la base: solo completa los idiomas que faltan (`TranslationImporter.save`, `overwrite=False`).
  Las capturas 02 a 04 se tomaron antes del arreglo y muestran *Savings Account*. Para revisar en
  STG antes y después del `-u`:
  `SELECT d.name, s.name FROM ir_model_fields_selection s JOIN ir_model_data d ON d.model = 'ir.model.fields.selection' AND d.res_id = s.id WHERE d.module = 'account_payment_dispersion';`
- **ACL de solo lectura.** `security/ir.model.access.csv` da lectura a
  `account.group_account_readonly` sobre las dispersiones y sus campos. En 17 no existía. Se
  mantiene: es el mismo patrón que usa el core para `account.payment` y permite que un usuario de
  solo lectura (auditor) vea el historial sin poder modificarlo.
- **`data/res.bank.csv` no se carga.** No está en `data` del manifiesto. Los bancos salen de
  `data/res_bank_data.xml` (`noupdate`, así que un `-u` no corrige cambios hechos a mano).
- **Columna "Activo" vacía en la lista de dispersiones.** La lista declara `active` con
  `invisible="1"`, que en listas oculta la celda pero no la columna (igual en 17). Se arregla con
  `column_invisible="1"`.
- **Textos del modelo en inglés.** El chatter de la dispersión dice "It shows the dispersions that
  have taken place over time. creado": usa la `_description` del modelo, que es una frase larga.
- **Cuentas no fiables.** En 19 una cuenta bancaria nueva sale como *No fiable* (etiqueta roja, sin
  *Enviar dinero*). Odoo solo bloquea el pago si el método exige cuenta; ningún método de Community
  lo exige, pero los módulos de banco podrían hacerlo.
- `static/description/icon.png` mide 300x300 px; los módulos del core usan 100x100 px.
