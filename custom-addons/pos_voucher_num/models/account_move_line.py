from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    vaucher_num_account = fields.Char(string="Voucher Number", store=True)
    pos_payment_id = fields.Many2one('pos.payment', string="POS Payment")
    super_voucher = fields.Char(
        string="Email del Cliente",
        related='pos_payment_id.vaucher_num',
        store=True  # Opcional: Si quieres que el campo sea indexado en la BD
    )