# -*- coding: utf-8 -*-
"""Adecúa las fórmulas de producción y los diarios al rediseño 19.

Reemplaza al script 19.0.1.0.1 del partner, que sobrescribía la fórmula
completa del celular con la del XML (que sí envía el teléfono) y cambiaba en
silencio una decisión de producción: el celular va siempre en blanco.

La configuración de campos es `noupdate`: el XML no toca los registros de
producción, por eso se corrigen aquí. Criterio: cambiar solo lo que en 19 ya
no existe y conservar el resto del código de producción.

1. Campo 10 "Celular Beneficiario": `res.partner.mobile` no existe en 19.
   Se reemplaza solo `object.partner_id.mobile or object.partner_id.phone` por
   `object.partner_id.phone`; la línea que fuerza el blanco se conserva.
2. Campos 8 y 9: `account.payment.ref` no existe en 19 (es `memo`; el pago ya
   no hereda de `account.move`). Se reemplaza `object.ref` por `object.memo`
   con límite de palabra.
3. Campo 2 "Nit Beneficiario": la fórmula de producción dejaba el NIT en
   blanco cuando no tenía guion. Se cambia por `document_number(...)` (helper
   de `account.batch.payment`), que conserva el corte por guion y, sin guion,
   quita el dígito de verificación solo si lo es. Solo se cambia si la fórmula
   sigue siendo la de producción conocida; si alguien la personalizó, se deja
   y queda un aviso en el log.
4. Método de pago en los diarios: solo en los que ya generaron dispersiones de
   Bancolombia en la v17 (en STG, el diario 17). Los diarios de tarjeta débito
   con banco Bancolombia (67, 69, 70, 71) no lo reciben: hoy no dispersan.

Idempotente: un segundo pase no encuentra nada que reemplazar. Conteos en el
log con _logger.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

PREFIX = 'bancolombia_payment_dispersal 19.0.1.0.3 post-migrate'
METHOD_CODE = 'bancolombia_dispersion'
OLD_MOBILE = 'object.partner_id.mobile or object.partner_id.phone'
NEW_MOBILE = 'object.partner_id.phone'
NIT_XMLID = 'bancolombia_payment_dispersal_field_beneficiary_nit'

# Fórmula del NIT de producción (v17), comparada sin espacios ni líneas vacías.
PROD_NIT_FORMULA = """
beneficiary_nit = ' '
if object.partner_id and object.partner_id.vat and object.partner_id.l10n_latam_identification_type_id:
    type_document = object.partner_id.l10n_latam_identification_type_id
    if '-' in object.partner_id.vat:
        beneficiary_nit=object.partner_id.vat.split('-')[0]
result = beneficiary_nit
"""

NEW_NIT_FORMULA = """beneficiary_nit = ' '
if object.partner_id and object.partner_id.vat and object.partner_id.l10n_latam_identification_type_id:
    # Sin dígito de verificación, sin puntos ni espacios (ver
    # account.batch.payment._bancolombia_document_number)
    beneficiary_nit = document_number(object.partner_id) or ' '
result = beneficiary_nit
"""


def _normalize(code):
    return [line.replace(' ', '') for line in (code or '').splitlines() if line.strip()]


def _fix_removed_fields(cr):
    cr.execute(
        """
        UPDATE bancolombia_payment_dispersal_field
           SET value = replace(value, %s, %s)
         WHERE value LIKE %s
        """,
        (OLD_MOBILE, NEW_MOBILE, '%' + OLD_MOBILE + '%'),
    )
    mobile_fixed = cr.rowcount
    cr.execute(
        r"""
        UPDATE bancolombia_payment_dispersal_field
           SET value = regexp_replace(value, 'object\.ref\M', 'object.memo', 'g')
         WHERE value ~ 'object\.ref\M'
        """
    )
    ref_fixed = cr.rowcount
    cr.execute(
        r"""
        SELECT count(*) FROM bancolombia_payment_dispersal_field
         WHERE value ~ 'partner_id\.mobile\M' OR value ~ 'object\.ref\M'
        """
    )
    remaining = cr.fetchone()[0]
    _logger.info(
        "%s: %s fórmulas con mobile corregidas, %s con ref→memo, %s restantes "
        "con campos inexistentes (se espera 0)",
        PREFIX, mobile_fixed, ref_fixed, remaining,
    )


def _fix_nit_formula(env):
    field = env.ref('bancolombia_payment_dispersal.%s' % NIT_XMLID, raise_if_not_found=False)
    if not field:
        _logger.warning("%s: no existe el campo %s; NIT sin cambios", PREFIX, NIT_XMLID)
        return
    if 'document_number(' in (field.value or ''):
        _logger.info("%s: la fórmula del NIT ya usa document_number", PREFIX)
        return
    if _normalize(field.value) != _normalize(PROD_NIT_FORMULA):
        _logger.warning(
            "%s: la fórmula del NIT (id %s) no es la de producción conocida; "
            "no se modifica. Revísela a mano: sin guion envía el NIT en blanco.",
            PREFIX, field.id,
        )
        return
    field.value = NEW_NIT_FORMULA
    _logger.info("%s: fórmula del NIT actualizada (id %s)", PREFIX, field.id)


def _add_method_to_journals(env):
    env.cr.execute(
        r"""
        SELECT DISTINCT journal_id FROM account_payment_dispersal
         WHERE name LIKE 'bancolombia\_dispersion%' AND journal_id IS NOT NULL
        """
    )
    journal_ids = [row[0] for row in env.cr.fetchall()]
    journals = env['account.journal'].browse(journal_ids).filtered(
        lambda journal: journal.type == 'bank'
    )
    if not journals:
        _logger.warning(
            "%s: ningún diario tiene dispersiones de Bancolombia; no se agrega "
            "el método. Agréguelo a mano en el diario que corresponda.",
            PREFIX,
        )
        return
    journals._ensure_dispersion_method_lines()
    journals._assign_dispersion_outstanding_accounts()
    lines = env['account.payment.method.line'].search([
        ('payment_method_id.code', '=', METHOD_CODE),
    ])
    for line in lines:
        _logger.info(
            "%s: método %s en diario %s (id %s)%s",
            PREFIX, METHOD_CODE, line.journal_id.name, line.journal_id.id,
            '' if line.journal_id in journals else ' — SIN dispersiones previas, revisar',
        )


def migrate(cr, version):
    if not version:
        # Instalación limpia: el XML crea los registros con el código nuevo.
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _fix_removed_fields(cr)
    _fix_nit_formula(env)
    _add_method_to_journals(env)
