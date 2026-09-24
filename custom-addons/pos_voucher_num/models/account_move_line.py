from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    voucher_num_account = fields.Char(string="Voucher Number", store=True)
    pos_payment_id = fields.Many2one('pos.payment', string="POS Payment")
    super_voucher = fields.Char(
        string="Voucher Number",
        related='pos_payment_id.voucher_num',
        store=True  # Opcional: Si quieres que el campo sea indexado en la BD
    )