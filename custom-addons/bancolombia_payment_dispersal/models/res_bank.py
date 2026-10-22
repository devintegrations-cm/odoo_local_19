# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResBank(models.Model):

    _inherit = 'res.bank'

    bancolombia_code = fields.Char(
        string='Código Bancolombia',
        help='Código del banco destino según la tabla de bancos de Bancolombia '
             '(ej: 5895142 para Davivienda).',
    )
