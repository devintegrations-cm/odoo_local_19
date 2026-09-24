# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    pos_vouchers_nums = fields.Char(
        string='POS Voucher Numbers',
        compute='_compute_pos_vouchers_nums',
        store=True,
        help='Voucher numbers from POS payments'
    )

    @api.depends('line_ids.pos_payment_id.voucher_num')
    def _compute_pos_vouchers_nums(self):
        for move in self:
            voucher_nums = []
            # Get voucher numbers from related POS payments
            for line in move.line_ids:
                if line.pos_payment_id and line.pos_payment_id.voucher_num:
                    voucher_nums.append(line.pos_payment_id.voucher_num)

            move.pos_vouchers_nums = ', '.join(voucher_nums) if voucher_nums else False
