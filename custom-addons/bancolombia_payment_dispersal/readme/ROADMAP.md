- **Post-migrate 19.0.1.0.1: corrige las fórmulas de bases que vienen de 17.** Las columnas se
  instalan con `noupdate`, así que el `-u` no las reescribe desde el XML. El script
  `migrations/19.0.1.0.1/post-migrate.py` recorre todas las filas (cualquier compañía, activas o
  archivadas) y cambia solo tres fragmentos: `object.ref` por `object.memo` (en 19 el pago ya no
  hereda del asiento), `reference = object.name` por `reference = object.name or '/'` (un borrador
  ya no tiene número), `object.name.split(` por `(object.name or '/').split(` (mismo caso, en
  fórmulas personalizadas como la *Referencia* de producción) y `X.mobile or X.phone` por `X.phone`
  (`res.partner.mobile` no existe en 19).
  El resto de la fórmula, editada a mano o no, queda igual. Es idempotente y solo corre al
  actualizar, no en una instalación nueva. Antes de tocar una fila guarda el valor original en
  `bk_bancolombia_dispersal_field_value_17` (`id`, `value`, `saved_at`; si se corre dos veces
  conserva el primero). Si una fórmula sigue usando `object.ref` o `.mobile` después del cambio,
  deja un `WARNING` en el log para revisarla a mano. Para revertir:
  `UPDATE bancolombia_payment_dispersal_field f SET value = b.value FROM bk_bancolombia_dispersal_field_value_17 b WHERE b.id = f.id;`
- **Consultas para STG, antes y después del `-u`.** Volumen:
  `SELECT count(*), count(*) FILTER (WHERE active) FROM bancolombia_payment_dispersal_field;` y
  `SELECT bancolombia_type_of_transaction, count(*) FROM account_payment GROUP BY 1;`.
  Fórmulas que aún usen lo que no existe en 19 (antes: las que va a corregir; después: tiene que dar
  0 filas):
  `SELECT id, value FROM bancolombia_payment_dispersal_field WHERE value ~ 'object\.ref\M|\.mobile\M';`.
  Respaldo después del `-u`: `SELECT count(*) FROM bk_bancolombia_dispersal_field_value_17;`.
  Pagos que en 17 llenaban *Documento Autorizado* con la referencia del asiento y en 19 la dejan en
  blanco: `SELECT count(*) FROM account_payment p JOIN account_move m ON m.id=p.move_id WHERE coalesce(m.ref,'')<>'' AND coalesce(p.memo,'')='';`.
  Contactos que tenían celular y no teléfono (si la columna `mobile` sigue en la base):
  `SELECT count(*) FROM res_partner WHERE coalesce(mobile,'')<>'' AND coalesce(phone,'')='';`.
- **Las acciones requieren `account.group_account_user`** (*Mostrar características de contabilidad
  completas*), igual que en 17. En Community ni *Contabilidad / Administrador* lo implica: en local
  el administrador no ve las acciones. En STG/producción hay contabilidad Enterprise, que puede
  darlo con sus roles: verificar en STG quién lo tiene:
  `SELECT u.login FROM res_users u JOIN res_groups_users_rel r ON r.uid=u.id WHERE r.gid=(SELECT res_id FROM ir_model_data WHERE module='account' AND name='group_account_user') AND u.active;`
- **Tipo de transacción calculado igual que en 17.** Se recalcula al cambiar proveedor o cuenta, solo
  en pagos salientes de diarios de banco y solo si la cuenta tiene tipo. Nunca vacía el campo: si la
  cuenta nueva no tiene tipo, queda el anterior. Un valor cargado a mano se respeta.
- **Pagos en borrador permitidos.** En 19 un borrador no tiene número (en 17 era `/`): la columna
  *Referencia* sale `/` y el aviso lo nombra *Borrador de pago (proveedor)*.
- **Fórmulas del XML igualadas a producción.** Solo afectan a instalaciones nuevas (en una base
  que se actualiza son `noupdate` y quedan las que tenga). *Nit Beneficiario* toma el número de
  identificación sin el dígito de verificación (`vat.split('-')[0]`), y *Documento Autorizado*,
  *Referencia* y *Celular Beneficiario* terminan en `' '`, como en STG 17. La base local conserva
  las originales del módulo, por eso la captura de la fórmula *Referencia* muestra la anterior.
- **NIT sin guion sale en blanco (heredado de producción 17).** Si el número de identificación no
  tiene guion, *Nit Beneficiario* queda `' '`: la fila no se corre, pero el banco puede rechazar la
  línea. En STG hay 26 proveedores así:
  `SELECT count(DISTINCT p.partner_id) FROM account_payment p JOIN res_partner rp ON rp.id = p.partner_id WHERE p.bancolombia_type_of_transaction IS NOT NULL AND coalesce(rp.vat,'') <> '' AND rp.vat NOT LIKE '%-%';`
- **Una celda vacía corre la fila (heredado de 17).** El archivo solo agrega una celda si la fórmula
  devuelve algo; si da vacío, las columnas siguientes se corren una a la izquierda. Todas las
  fórmulas que trae el módulo arrancan en `' '` para evitarlo; hay que cuidarlo al editar una.
- **Código Bancolombia sin uso (heredado de 17).** La columna *Código Banco* y la validación usan
  el **Código** del banco (`res.bank.code`, 4 dígitos). El campo **Código Bancolombia**
  (`bancolombia_code`, 7 dígitos, cargado en 14 bancos) no lo usa nada.
- **Menores heredados de 17, sin tocar.** La columna *Activo* de la lista de campos sale vacía
  porque declara `invisible` en vez de `column_invisible`. `models/account_payment.py` hace
  `import unidecode` sin usarlo, y el manifiesto lo exige como dependencia externa. El nombre del
  beneficiario se corta a 29 caracteres cuando pasa de 30, sin pasar a mayúsculas el recorte (salvo
  que tenga Ñ) y sin quitar tildes. *NIT PAGADOR* quita los dos últimos caracteres del NIT de la
  compañía (asume el formato `900123456-7`); en local la compañía no tiene NIT y la celda sale vacía.
- **Traducciones.** *Manager's Check Payment* (36) no tiene traducción, *Abono  cta Corriente* (27)
  tiene un doble espacio, y el chatter de las columnas dice "Configuration of the fields to be
  displayed in the excel file for payments in bancolombia creado".
- `static/description/icon.png` mide 300x300 px; los módulos del core usan 100x100 px.
