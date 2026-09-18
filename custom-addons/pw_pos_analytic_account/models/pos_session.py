# -*- coding: utf-8 -*-
from odoo import models, fields


class PosSession(models.Model):
    _inherit = 'pos.session'

    account_analytic_id = fields.Many2one('account.analytic.account',
        related="config_id.account_analytic_id",
        store=True, string='Analytic Account', copy=False
    )

    def _get_analytic_distribution(self):
        """Distribución analítica derivada de la cuenta configurada en el punto de venta."""
        self.ensure_one()
        if not self.account_analytic_id:
            return False
        return {self.account_analytic_id.id: 100}

    def _get_sale_vals(self, key, sale_vals):
        # Odoo 19: la línea contable de venta del pedido se arma acá.
        # (en 17 este módulo enganchaba `_prepare_line`, que ya no existe y que
        # además descartaba la clave `analytic_distribution`).
        res = super()._get_sale_vals(key, sale_vals)
        distribution = self._get_analytic_distribution()
        if distribution:
            res['analytic_distribution'] = distribution
        return res

    def _get_stock_expense_vals(self, exp_account, amount, amount_converted):
        res = super()._get_stock_expense_vals(exp_account, amount, amount_converted)
        distribution = self._get_analytic_distribution()
        if distribution:
            res['analytic_distribution'] = distribution
        return res

    def _get_stock_valuation_vals(self, stock_val_account, amount, amount_converted):
        # Odoo 19: renombrado desde `_get_stock_output_vals` (17).
        res = super()._get_stock_valuation_vals(stock_val_account, amount, amount_converted)
        distribution = self._get_analytic_distribution()
        if distribution:
            res['analytic_distribution'] = distribution
        return res

    def _get_invoice_receivable_vals(self, amount, amount_converted):
        res = super()._get_invoice_receivable_vals(amount, amount_converted)
        distribution = self._get_analytic_distribution()
        if distribution:
            res['analytic_distribution'] = distribution
        return res

    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        res = super()._validate_session(
            balancing_account=balancing_account,
            amount_to_balance=amount_to_balance,
            bank_payment_method_diffs=bank_payment_method_diffs,
        )
        distribution = self._get_analytic_distribution()
        if distribution:
            all_moves = self._get_related_account_moves()
            all_moves.line_ids.write({'analytic_distribution': distribution})
        return res
