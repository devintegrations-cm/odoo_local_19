# -*- coding: utf-8 -*-
"""Adecúa los datos de producción al rediseño 19 (O1 y O2 del plan QA).

O1 — Campo 10 "Tipo de cuentas de destino": el código de producción en la
tabla `bancodeoccidente_payment_dispersal_field` usa
`partner_bank_id.type_of_account`, que en 19 ya no existe en
`res.partner.bank` (se renombró a `co_account_type`). Con esa referencia el
archivo no se genera (el error de safe_eval termina en UserError). El XML del
módulo ya usa el campo nuevo, pero es `noupdate`: no toca los registros
existentes, de ahí este UPDATE. Solo se reemplaza la subcadena dentro de
`value`; el resto del código (NIT, nombre, banco, fecha…) no se toca. Se
aplica a TODOS los registros, incluidos los inactivos. Idempotente: un
segundo pase no encuentra la subcadena.

O2 — Los diarios de Occidente existentes no reciben el método de pago de
dispersión: el cálculo del core no se recalcula para registros existentes y
el `write` del diario solo actúa si cambia banco/nombre. Sin el método no se
puede armar el lote. Se usa el hook del módulo base
(`_ensure_dispersion_method_lines`), que asigna el método solo a los diarios
cuyo banco coincide con Occidente (código 1023, BIC OCCICOBC… o nombre).
`account.payment.method.line.code` es related no almacenado: la búsqueda se
hace por `payment_method_id.code`.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

OCCIDENTE_METHOD_CODE = 'banco_occidente_dispersion'
OLD_FIELD = 'partner_bank_id.type_of_account'
NEW_FIELD = 'partner_bank_id.co_account_type'


def migrate(cr, version):
    if not version:
        # Instalación limpia: el XML (noupdate) crea los registros con el
        # código nuevo y los diarios pasan por los hooks de create.
        return

    # ------------------------------------------------------------------ O1
    cr.execute(
        """
        SELECT count(*) FROM bancodeoccidente_payment_dispersal_field
         WHERE value LIKE %s
        """,
        ('%' + OLD_FIELD + '%',),
    )
    before = cr.fetchone()[0]
    cr.execute(
        """
        UPDATE bancodeoccidente_payment_dispersal_field
           SET value = replace(value, %s, %s)
         WHERE value LIKE %s
        """,
        (OLD_FIELD, NEW_FIELD, '%' + OLD_FIELD + '%'),
    )
    fixed = cr.rowcount
    cr.execute(
        """
        SELECT count(*) FROM bancodeoccidente_payment_dispersal_field
         WHERE value LIKE %s
        """,
        ('%' + OLD_FIELD + '%',),
    )
    after = cr.fetchone()[0]
    _logger.info(
        "banco_de_occidente_payment_dispersal 19.0.1.0.3 post-migrate: %s "
        "registros con %s, %s corregidos, %s restantes (se espera 0)",
        before, OLD_FIELD, fixed, after,
    )

    # ------------------------------------------------------------------ O2
    env = api.Environment(cr, SUPERUSER_ID, {})
    journals = env['account.journal'].search([('type', '=', 'bank')])
    journals._ensure_dispersion_method_lines()
    journals._assign_dispersion_outstanding_accounts()
    lines = env['account.payment.method.line'].search([
        ('payment_method_id.code', '=', OCCIDENTE_METHOD_CODE),
    ])
    if lines:
        for line in lines:
            _logger.info(
                "banco_de_occidente_payment_dispersal 19.0.1.0.3 post-migrate: "
                "método %s en diario %s (banco: %s)",
                OCCIDENTE_METHOD_CODE, line.journal_id.name,
                line.journal_id.bank_id.name or 'sin banco',
            )
    else:
        _logger.warning(
            "banco_de_occidente_payment_dispersal 19.0.1.0.3 post-migrate: "
            "ningún diario recibió el método %s; verifique que los diarios "
            "de Occidente tengan su banco asociado (código 1023 u OCCICOBC)",
            OCCIDENTE_METHOD_CODE,
        )
