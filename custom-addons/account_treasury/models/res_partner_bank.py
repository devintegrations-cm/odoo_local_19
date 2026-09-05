# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    bank_account_types = [
        ('','Seleccione Una Opcion'),
        ('ahorros', 'Ahorros'),
        ('corriente', 'Corriente')
    ]
    
    bank_account_type_col = fields.Selection(
        selection=bank_account_types,
        string='Tipo de cuenta bancaria',
        required=True,
        default='',
        help="Seleccione el tipo de cuenta"
    )

    #bank_account_type_col = fields.Many2one(tracking=True)