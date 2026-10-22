# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResBank(models.Model):

    _inherit = 'res.bank'

    code = fields.Char(
        string='Código Superfinanciera',
        help='Código de la entidad ante la Superintendencia Financiera de Colombia '
             '(4 dígitos, ej: 1051 para Davivienda, 1013 para BBVA).',
    )
    dispersal_code = fields.Char(
        string='Código de Dispersión',
        help='Código del banco que se escribe en los archivos planos de dispersión. '
             'Cada formato toma los últimos dígitos que necesita '
             '(ej: 000051 para Davivienda, 000013 para BBVA).',
    )
