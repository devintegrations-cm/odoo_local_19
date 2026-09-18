# -*- coding: utf-8 -*-
from odoo import models, fields, api


class PosOrder(models.Model):
    _inherit = 'pos.order'

    account_analytic_id = fields.Many2one('account.analytic.account',
        related="session_id.account_analytic_id",
        copy=False, store=True, string='Analytic Account')

    @api.model
    def _get_invoice_lines_values(self, line_values, pos_line, move_type):
        # Odoo 19: los valores de la línea de factura del pedido se arman acá
        # (en 17 este módulo enganchaba `_prepare_invoice_line`, que nunca existió
        # en `pos.order`: el override estaba muerto ya en 17).
        res = super()._get_invoice_lines_values(line_values, pos_line, move_type)
        if res.get('display_type'):
            # secciones de combo: no llevan analítica
            return res
        analytic_account = pos_line.order_id.account_analytic_id
        if analytic_account:
            res['analytic_distribution'] = {analytic_account.id: 100}
        return res


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    account_analytic_id = fields.Many2one('account.analytic.account',
        related="order_id.account_analytic_id", string='Analytic Account')
