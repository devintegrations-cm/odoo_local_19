# -*- coding: utf-8 -*-

from odoo import models, fields, _


class PosOrder(models.Model):
    _inherit = 'pos.config'

    iface_tippercent = fields.Boolean(string="POS Tip % Button")
    # tip_percent_ids = fields.Many2many('pos.tip', string='Tip %')
    tip_percent1 = fields.Float(string='Tip1 %')
    tip_percent2 = fields.Float(string='Tip2 %')
    tip_percent3 = fields.Float(string='Tip3 %')


# class POSTip(models.Model):
#     _name = "pos.tip"
#
#     name = fields.Float(string='Tip %')

