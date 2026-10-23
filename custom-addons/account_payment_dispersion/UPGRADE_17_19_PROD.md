# Upgrade de producción 17 → 19 — `account_payment_dispersion`

Runbook de la migración del módulo base. Los módulos de banco
(`bancolombia_payment_dispersal`, `banco_de_occidente_payment_dispersal`) se
revisan aparte con el mismo criterio.

**Criterio**: cero pérdida de datos. Los scripts de `migrations/19.0.1.0.4/`
son idempotentes; las acciones de esta lista son de **datos propios** y se
aplican con aprobación de tesorería, registrando los conteos antes/después.

## 1. Saneo previo al upgrade (se ejecuta en 17)

### 1.1 Cuentas con espacio no separable (NBSP, U+00A0) — 38 cuentas

Algunos números de cuenta terminan en un NBSP; la validación de la 19 usa
`sanitized_acc_number` y las tolera, pero el dato queda sucio. Antes de
limpiar, revisar que no se genere ningún duplicado.

Ojo con la expresión regular: en PostgreSQL `[[:space:]]` **no** incluye el
NBSP (U+00A0) ni con la collation de la base; por eso se usa
`'[' || chr(160) || ' ]+$'`, que sí lo matchea (y también un espacio normal
final, que no hace daño quitar).

```sql
-- Antes (conteo esperado: 38)
SELECT count(*) FROM res_partner_bank
 WHERE acc_number ~ ('[' || chr(160) || ' ]+$') AND bank_id IN (
       SELECT res_id FROM ir_model_data
        WHERE model = 'res.bank' AND module = 'account_payment_dispersion');

-- Duplicados potenciales tras la limpieza (debe devolver 0 filas)
SELECT b2.acc_number, count(*) FROM res_partner_bank b1
  JOIN res_partner_bank b2
    ON b2.partner_id = b1.partner_id
   AND regexp_replace(b2.acc_number, '[' || chr(160) || ' ]+$', '') = regexp_replace(b1.acc_number, '[' || chr(160) || ' ]+$', '')
   AND b2.id <> b1.id
 WHERE b1.acc_number ~ ('[' || chr(160) || ' ]+$')
 GROUP BY b2.acc_number;

-- Limpieza (solo si el chequeo anterior está vacío)
UPDATE res_partner_bank
   SET acc_number = regexp_replace(acc_number, '[' || chr(160) || ' ]+$', '')
 WHERE acc_number ~ ('[' || chr(160) || ' ]+$');

-- Después (conteo: 0)
SELECT count(*) FROM res_partner_bank WHERE acc_number ~ ('[' || chr(160) || ' ]+$');
```

Nota: el `UPDATE` por SQL no recalcula `sanitized_acc_number`, pero no hace
falta: el `sanitize_account_number` de la 17 y de la 19 (`re.sub(r'\W+', '')`)
ya excluía el NBSP, así que el valor sanitizado no cambia y tampoco puede
aparecer un duplicado nuevo en la restricción `unique(sanitized_acc_number,
partner_id)`.

### 1.2 Cuenta 5424 MADIAUTOS (Davivienda, sin tipo) — tesorería define el tipo

```sql
-- Antes: 1 fila (en 17 la columna se llama type_of_account)
SELECT id, acc_number, type_of_account FROM res_partner_bank WHERE id = 5424;
-- Acción de tesorería (ejemplo con ahorros):
-- UPDATE res_partner_bank SET type_of_account = 'savings_account' WHERE id = 5424;
```

### 1.3 Cuenta 5221 DALLA CORTE (Deutsche Bank, `no_account`) — se deja vacía

Pago al exterior que no va por archivo plano. Tras el upgrade quedará con
`co_account_type` NULL. Sin acción.

### 1.4 ITAU duplicado (ids 2 y 11) — pasar la cuenta al ITAU oficial

```sql
-- Antes
SELECT b.id, b.name, b.code, b.bic,
       (SELECT count(*) FROM res_partner_bank pb WHERE pb.bank_id = b.id) AS cuentas
  FROM res_bank b WHERE b.id IN (2, 11);

-- Mover las cuentas del banco 2 (sin código) al 11 (código 1014)
UPDATE res_partner_bank SET bank_id = 11 WHERE bank_id = 2;

-- Archivar el banco duplicado (res.bank tiene active en 17 y en 19; NO
-- borrar: el id 2 fue creado a mano y un DELETE por SQL es innecesario)
UPDATE res_bank SET active = false WHERE id = 2;

-- Después: 0 cuentas en el banco 2 y el banco archivado
SELECT count(*) FROM res_partner_bank WHERE bank_id = 2;
SELECT id, name, active FROM res_bank WHERE id = 2;
```

### 1.5 NU (id 72, código 1809, 5 cuentas) — asignar dispersal_code

```sql
-- Antes (dispersal_code NULL)
SELECT id, name, code, dispersal_code FROM res_bank WHERE id = 72;
-- Acción (confirmar el código 001809 con el banco antes):
UPDATE res_bank SET dispersal_code = '001809' WHERE id = 72;
```

## 2. Upgrade del módulo

En la plataforma (STG primero, producción después):

1. Backup de la base.
2. Actualizar módulos: `account_payment_dispersion` (arrastra las migraciones
   `19.0.1.0.4`: copia `type_of_account` → `co_account_type` y carga
   `dispersal_code` en los bancos del módulo).
3. Revisar el log de la migración (con `_logger`, visible en el log de
   odoo.sh o del servidor):

   - `pre-migrate: 1 vista de contactos huérfana desactivada` — la vista
     `..._partner_property_form` de la v17, que usa `type_of_account` y ya no
     está en el XML de la 19. Se desactiva (no se borra) y Odoo la elimina al
     final del upgrade. En bases sin datos de 17 el conteo es 0.
   - `pre-migrate: ... cuentas candidatas, ... copiadas a co_account_type,
     ... con tipo antiguo no admitido` — se espera ~1.624 copiadas y **1 o 2**
     sin admitir: siempre la 5221 (`no_account`); la 5424 (MADIAUTOS) solo si
     su tipo está guardado como un valor no vacío — si está NULL, no entra en
     ese conteo (y entonces el log dirá 1).
   - `...: 67 bancos con código de dispersión cargado, 1 con BIC HSBC México
     corregido, 1 pendientes (se espera 1: HSBC res_bank_1010, sin código en
     el XML)`.

   Aclaración: el XML define los **mismos 68 bancos** que ya existen en
   producción (los 135 `<record>` son esos 68 del bloque de bancos más 67
   que solo cargan el código); el upgrade **no crea bancos nuevos**. El
   único banco del XML sin código de dispersión es HSBC (`res_bank_1010`,
   no es banco de dispersión) — ese es el "1 pendiente" del log. NU (id 72,
   creado a mano, sin xmlid) **no entra en ese conteo**: su estado se
   verifica aparte con la consulta de §1.5.

## 3. Verificación posterior (en 19)

```sql
-- Tipos de cuenta copiados. Sin filtro de bancos: hay que contar TODAS las
-- cuentas para comparar contra los 1.627 de antes (el filtro por bancos del
-- módulo deja afuera las 5 cuentas de NU y cualquier banco manual).
SELECT co_account_type, active, count(*) FROM res_partner_bank GROUP BY 1, 2;
-- Se espera: savings_account ~1.270+2, current_account ~354+1, NULL: la
-- cuenta 5221 (DALLA CORTE, no_account), la 5424 (MADIAUTOS, si sigue sin
-- tipo) y cualquier cuenta que en 17 no tuviera tipo.

-- Bancos del módulo con código de dispersión (se espera: 67 de 68; sin
-- código solo HSBC res_bank_1010)
SELECT count(*) FROM res_bank
 WHERE id IN (SELECT res_id FROM ir_model_data
               WHERE model = 'res.bank' AND module = 'account_payment_dispersion')
   AND dispersal_code IS NOT NULL;

-- NU (id 72, creado a mano): debe tener su código asignado en §1.5
SELECT id, name, code, dispersal_code, active FROM res_bank WHERE id = 72;

-- Dispersiones históricas consultables (menú Contabilidad → Proveedores)
SELECT count(*) FROM account_payment_dispersal;  -- se espera: 581

-- Líneas de pago del diario 294 (en 19, account.payment.method.line.code es
-- un related no almacenado: la tabla NO tiene esa columna, hay que unir con
-- account.payment.method; la consulta con JOIN funciona en 17 y en 19).
-- El conteo total es 23: 22 con cuenta contable + 1 sin ella. Esas 22 con
-- cuenta son las que Command.clear() del cálculo ponía en riesgo. Tras el
-- upgrade debe mantenerse el mismo desglose.
SELECT (l.payment_account_id IS NOT NULL) AS con_cuenta, count(*)
  FROM account_payment_method_line l
  JOIN account_payment_method m ON m.id = l.payment_method_id
 WHERE l.journal_id = 294 AND m.code = 'manual'
 GROUP BY 1;
-- Se espera: con_cuenta = 22, sin cuenta (con_cuenta = false) = 1
-- (línea base de 17: comparar contra esta consulta tras el upgrade)

-- NBSP residual (se espera: 0)
SELECT count(*) FROM res_partner_bank WHERE acc_number ~ ('[' || chr(160) || ' ]+$');
```

## 4. Fuera de alcance (revisión de bancos, después)

- Los `account.payment.dispersal_field` de Bancolombia/Occidente referencian
  `partner_bank_id.type_of_account` en sus fórmulas: al renombrar el campo a
  `co_account_type` esas fórmulas deben actualizarse en cada módulo de banco.
- Los scripts `post-migrate` que adjuntan métodos de dispersión a diarios
  (`_ensure_dispersion_method_lines`) viven desde ahora en cada módulo de
  banco, no en el base.
- Origen del NIT en los campos de archivo de cada banco: usar
  `commercial_partner_id.vat` (mismo criterio que B1 del alcance).

## 5. Verificación funcional en STG (post-upgrade)

Pruebas que tocan `account_batch_payment` (Enterprise) y no se pueden correr
en local. Se hacen en STG antes de llevar el cambio a producción.

### 5.1 Rollback de lotes al fallar un grupo (B4)

Al crear lotes desde varios grupos (dos diarios/métodos distintos), si un
grupo tiene error (p. ej. un pago con cuenta sin tipo), el módulo revierte
los lotes ya creados antes de mostrar el asistente de error.

Prueba: seleccionar pagos de dos diarios (p. ej. Occidente y Bancolombia)
donde el segundo grupo tenga un pago con error y comprobar que:

1. **No queda ningún lote creado** (antes del fix quedaba el del primer
   grupo, que había que borrar a mano).
2. Un usuario de Facturación (`account.group_account_invoice`) puede
   ejecutar el flujo sin `AccessError` en el `unlink` de los lotes; si no
   tiene permiso de borrar, el usuario vería ese error en vez del asistente
   — en ese caso ajustar `ir.model.access` de `account.batch.payment`.
3. Si en el asistente de error el usuario elige "crear de todos modos" o
   "excluir pagos", el asistente crea **solo** el lote del grupo que falló:
   los grupos anteriores ya se revirtieron y hay que volver a seleccionarlos.
   Avisárselo a tesorería.

### 5.2 Métodos de dispersión en diarios existentes (B3/A3)

Al quitar el override del cálculo, nada agrega los métodos de dispersión a
los diarios **existentes** durante el upgrade (el cálculo del core no se
recalcula para registros existentes y el `write` del diario solo actúa si
cambia `bank_id`, `bank_account_id` o `name`). Eso le toca al post-migrate
de cada módulo de banco (§4). Después del upgrade se comprueba:

```sql
SELECT j.id, j.name::text, m.code FROM account_payment_method_line l
  JOIN account_payment_method m ON m.id = l.payment_method_id
  JOIN account_journal j ON j.id = l.journal_id
 WHERE m.payment_type = 'outbound' AND m.code <> 'manual' ORDER BY 1;
```

Se espera: los diarios de Occidente Bogotá y Cartagena con el método de
Occidente; el de Bancolombia y los 67, 69, 70 y 71 con Bancolombia; el 294
con sus 23 líneas manuales intactas (22 con cuenta contable + 1 sin ella,
ver el desglose de §3). Si los métodos no aparecen, es trabajo del
post-migrate de cada módulo de banco, no del base.
