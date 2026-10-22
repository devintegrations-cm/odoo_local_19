# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.fields import Domain


class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_colombian_dispersion_bank_codes(self):
        """Map dispersal methods to the origin bank they belong to.

        Each bank module extends this hook:

            {
                'bancolombia_dispersion': {
                    'codes': ('1007',),
                    'bic_prefixes': ('COLOCOBM',),
                    'name_fragments': ('BANCOLOMBIA',),
                },
            }

        ``codes`` are Superintendencia Financiera codes on ``res.bank.code``.
        ``bic_prefixes`` match ``res.bank.bic`` when the official code is missing.
        ``name_fragments`` match the journal or bank name (case insensitive).
        """
        return {}

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        country_id = self.env.ref('base.co').id
        for code in self._get_colombian_dispersion_bank_codes():
            res[code] = {
                'mode': 'multi',
                'type': ('bank',),
                'country_id': country_id,
            }
        return res

    @api.model
    def _get_dispersion_bank_domain(self, code):
        info = self._get_colombian_dispersion_bank_codes().get(code)
        if not info:
            return Domain.TRUE
        domain = Domain.FALSE
        if info.get('codes'):
            domain |= Domain('bank_id.code', 'in', list(info['codes']))
        for prefix in info.get('bic_prefixes') or ():
            domain |= Domain('bank_id.bic', '=like', f'{prefix}%')
        for fragment in info.get('name_fragments') or ():
            domain |= Domain('bank_id.name', 'ilike', fragment)
            domain |= Domain('name', 'ilike', fragment)
        return domain

    @api.model
    def _journal_matches_dispersion_bank(self, journal, code):
        info = self._get_colombian_dispersion_bank_codes().get(code)
        if not info:
            return False
        if journal.bank_id:
            bank_code = journal.bank_id.code
            if bank_code and bank_code in (info.get('codes') or ()):
                return True
            bic = journal.bank_id.bic or ''
            if any(bic.startswith(prefix) for prefix in (info.get('bic_prefixes') or ())):
                return True
            bank_name = (journal.bank_id.name or '').upper()
            if any(fragment.upper() in bank_name for fragment in (info.get('name_fragments') or ())):
                return True
        journal_name = (journal.name or '').upper()
        return any(fragment.upper() in journal_name for fragment in (info.get('name_fragments') or ()))

    @api.model
    def _get_payment_method_domain(self, code, with_currency=True, with_country=True):
        domain = super()._get_payment_method_domain(code, with_currency, with_country)
        if code in self._get_colombian_dispersion_bank_codes():
            domain &= self._get_dispersion_bank_domain(code)
        return domain

    def _auto_link_payment_methods(self, payment_methods, methods_info):
        payment_methods = super()._auto_link_payment_methods(payment_methods, methods_info)
        journals = self.env['account.journal'].search([('type', '=', 'bank')])
        journals._ensure_dispersion_method_lines()
        journals._assign_dispersion_outstanding_accounts()
        return payment_methods
